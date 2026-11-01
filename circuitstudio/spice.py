"""Limited CircuitDSL RC transient deck generation and ngspice adapter."""

import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .analysis import parse_quantity

MAX_NETLIST_BYTES = 1_000_000
MAX_SIM_OUTPUT_BYTES = 32_000_000


def find_ngspice():
    configured = os.environ.get("NGSPICE")
    candidates = [configured, shutil.which("ngspice")]
    roots = [Path(__file__).resolve().parents[1] / "tools", Path(sys.executable).resolve().parent / "tools"]
    if platform.system() == "Windows":
        for root in roots:
            for relative in (Path("ngspice-47/bin/ngspice.exe"), Path("ngspice/bin/ngspice.exe"),
                             Path("Spice64/bin/ngspice.exe")):
                candidates.append(str(root / relative))
            if root.is_dir():
                candidates.extend(str(path) for path in root.glob("**/ngspice.exe"))
        return next((candidate for candidate in candidates
                     if candidate and Path(candidate).is_file()), None)
    for root in roots:
        for relative in (Path("ngspice-47/bin/ngspice"), Path("ngspice/bin/ngspice"),
                         Path("Spice64/bin/ngspice")):
            candidates.append(str(root / relative))
        if root.is_dir():
            candidates.extend(str(path) for path in root.glob("**/ngspice"))
    return next((candidate for candidate in candidates
                 if candidate and Path(candidate).suffix.lower() != ".exe"
                 and Path(candidate).is_file() and os.access(candidate, os.X_OK)), None)


def generate_spice_deck(data):
    """Generate only an explicit, ideal passive R/C transient circuit; no model is invented."""
    simulation = data.get("simulation")
    if data.get("schema_version") != 2 or not simulation:
        raise ValueError("CircuitDSL v2でsimulation条件を指定してください。")
    nets = {net["name"]: net for net in data.get("nets", [])}
    grounds = [name for name, net in nets.items() if net.get("kind") == "ground"]
    if len(grounds) != 1:
        raise ValueError("SPICEは基準GNDネットが1個の場合のみ生成します。")
    ground = grounds[0]
    source = simulation["source"]
    if source["negative_net"] != ground or source["positive_net"] not in nets or source["positive_net"] == ground:
        raise ValueError("SPICE電圧源は宣言済みの正電源ネットと唯一のGND間に指定してください。")
    observe = simulation["observe_nets"]
    if any(name not in nets for name in observe):
        raise ValueError("simulation.observe_nets は宣言済みネットを指定してください。")
    node_names = {ground: "0"}
    for index, name in enumerate(sorted(nets), 1):
        if name != ground:
            node_names[name] = f"N{index:03d}"
    components = data.get("components", [])
    spice_components = []
    for component in components:
        symbol = component["symbol"]
        if symbol == "Connector:Conn_01x02_Pin":
            continue
        if symbol not in {"Device:R", "Device:C"}:
            raise ValueError(f"{component['ref']} ({symbol}) のSPICEモデルがありません。")
        if set(component.get("pins", {})) != {"1", "2"}:
            raise ValueError(f"{component['ref']} の両端ネットを指定してください。")
        value = component["value"]
        if isinstance(value, str):
            match = re.fullmatch(r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*(?:([pnuµμmMkKG])\s*)?(Ohms|Ohm|ohm|Ω|Ω|F|V|A|W|H|s)?\s*", value)
            if not match:
                raise ValueError(f"{component['ref']} の値/単位をSPICEで解釈できません: {value}")
            unit = match.group(3)
            expected_units = {"Ohms", "Ohm", "ohm", "Ω", "Ω"} if symbol == "Device:R" else {"F"}
            if unit and unit not in expected_units:
                raise ValueError(f"{component['ref']} の単位が部品種別と一致しません。")
        numeric = parse_quantity(value)
        if numeric is None or not math.isfinite(numeric) or numeric <= 0:
            raise ValueError(f"{component['ref']} の値は正の有限値が必要です。")
        ref = component["ref"]
        spice_components.append(f"{ref} {node_names[component['pins']['1']]} {node_names[component['pins']['2']]} {numeric:.12g}")
    if not spice_components:
        raise ValueError("シミュレーション可能な抵抗/コンデンサがありません。")
    step, stop = simulation["step_s"], simulation["stop_s"]
    values = [source[key] for key in ("initial_voltage_V", "pulsed_voltage_V", "delay_s", "rise_s", "fall_s", "pulse_width_s", "period_s")]
    pulse = " ".join(f"{value:.12g}" for value in values)
    observed = " ".join(f"v({node_names[name]})" for name in observe)
    lines = [f"* CircuitStudio RC transient; ideal passive models only", f"VSTIM {node_names[source['positive_net']]} 0 PULSE({pulse})"]
    lines.extend(spice_components)
    lines.extend([".control", "set wr_vecnames", "set wr_singlescale", f"tran {step:.12g} {stop:.12g}",
                  f"wrdata transient.csv {observed}", "quit", ".endc", ".end"])
    return "\n".join(lines) + "\n"


def _safe_netlist_outputs(path):
    outputs, visited = [], set()
    parent = path.parent.resolve()
    allowed_commands = {"set", "tran", "ac", "op", "dc", "wrdata", "print", "meas", "let", "linearize", "quit"}

    def scan(source):
        resolved = source.resolve()
        if not resolved.is_relative_to(parent):
            raise ValueError("SPICEモデル参照は選択したネットリストのフォルダー内に限定します。")
        if not resolved.is_file():
            raise ValueError(f"SPICEモデルファイルが見つかりません: {resolved.name}")
        if resolved in visited:
            return
        if len(visited) >= 64:
            raise ValueError("SPICEモデル参照数が64件上限を超えています。")
        visited.add(resolved)
        if sum(item.stat().st_size for item in visited) > 8_000_000:
            raise ValueError("SPICEネットリストとモデル合計が8 MB上限を超えています。")
        text = resolved.read_text(encoding="utf-8-sig")
        in_control = False
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("*", "#")):
                continue
            if stripped.casefold() == ".control":
                in_control = True
                continue
            if stripped.casefold() == ".endc":
                in_control = False
                continue
            if in_control:
                command = stripped.split(None, 1)[0].casefold()
                if command not in allowed_commands:
                    raise ValueError(f"SPICE制御コマンド '{command}' は安全のため実行しません。")
                match = re.match(r"(?i)^wrdata\s+(?:\"([^\"]+)\"|(\S+))", stripped)
                if match:
                    name = match.group(1) or match.group(2)
                    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", name) or name in {".", ".."}:
                        raise ValueError("wrdataの出力先は安全なファイル名のみ指定できます。")
                    output = (parent / name).resolve()
                    if not output.is_relative_to(parent):
                        raise ValueError("SPICE出力先がネットリストのフォルダー外です。")
                    if output.exists():
                        raise FileExistsError(f"SPICE出力を上書きしないため停止しました: {output}")
                    if output in outputs:
                        raise ValueError("同一SPICE出力ファイルを複数回指定できません。")
                    outputs.append(output)
                continue
            match = re.match(r"(?i)^\.(?:include|lib)\s+(?:\"([^\"]+)\"|(\S+))", stripped)
            if match:
                include = Path(match.group(1) or match.group(2))
                scan(include if include.is_absolute() else resolved.parent / include)

    scan(path)
    return outputs


def simulate(netlist_path, timeout=60):
    path = Path(netlist_path).resolve(strict=True)
    if path.suffix.lower() not in {".cir", ".sp", ".spi", ".spice"}:
        raise ValueError("SPICEネットリスト (.cir/.sp/.spi/.spice) を指定してください。")
    if path.stat().st_size > MAX_NETLIST_BYTES:
        raise ValueError("SPICEネットリストが1 MB上限を超えています。")
    if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 600:
        raise ValueError("SPICE timeout は0より大きく600秒以下にしてください。")
    try:
        outputs = _safe_netlist_outputs(path)
    except (FileExistsError, ValueError) as exc:
        return {"status": "BLOCKED", "reason": str(exc)}
    executable = find_ngspice()
    if not executable:
        return {"status": "NOT_EXECUTED", "reason": "ngspiceが見つかりません。波形は生成していません。"}
    with tempfile.TemporaryDirectory(prefix="circuitstudio-spice-") as temp:
        output = Path(temp) / "ngspice.log"
        try:
            result = subprocess.run([executable, "-n", "-b", "-o", str(output), str(path)], capture_output=True, text=True,
                                    timeout=timeout, check=False, shell=False, cwd=str(path.parent))
        except subprocess.TimeoutExpired:
            return {"status": "NOT_EXECUTED", "reason": f"ngspice timeout ({timeout}s)"}
        oversized = [str(item) for item in outputs if item.exists() and item.stat().st_size > MAX_SIM_OUTPUT_BYTES]
        created = [str(item) for item in outputs if item.is_file() and item.stat().st_size <= MAX_SIM_OUTPUT_BYTES]
        return {"status": "PASS" if result.returncode == 0 and not oversized else "FAIL", "returncode": result.returncode,
                "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:],
                "log": output.read_text(encoding="utf-8", errors="replace")[-8000:] if output.exists() else "",
                "csv_outputs": created, "oversized_outputs": oversized}
