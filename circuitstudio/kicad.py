"""Self-contained KiCad schematic/project generation and native CLI wrappers."""

import csv
import html
import json
import math
import os
import shutil
import subprocess
import tempfile
import uuid
from functools import lru_cache
from pathlib import Path

from .analysis import analyze
from .catalog import SYMBOLS
from .dsl import circuit_json, safe_project_stem
from .sexpr import children, require_root

FORMAT_VERSION = 20250114


def _id():
    return str(uuid.uuid4())


def _q(text):
    return json.dumps(str(text), ensure_ascii=False)


def _effects(justify="", hidden=False):
    j = f" (justify {justify})" if justify else ""
    h = " hide" if hidden else ""
    return f"(effects (font (size 1.27 1.27)){j}{h})"


def _lib_symbol(symbol_id):
    root, name = symbol_id.split(":", 1)
    info = SYMBOLS[symbol_id]
    label = name.replace("_", " ")
    if info["shape"] == "resistor":
        graphic = '(rectangle (start -2.54 1.27) (end 2.54 -1.27) (stroke (width 0) (type default)) (fill (type none)))'
    elif info["shape"] == "capacitor":
        graphic = '(polyline (pts (xy -0.8 2.0) (xy -0.8 -2.0)) (stroke (width 0.5) (type default)) (fill (type none))) (polyline (pts (xy 0.8 2.0) (xy 0.8 -2.0)) (stroke (width 0.5) (type default)) (fill (type none)))'
    elif info["shape"] == "led":
        graphic = '(rectangle (start -2.54 1.27) (end 2.54 -1.27) (stroke (width 0.25) (type default)) (fill (type none)))'
    else:
        graphic = f'(rectangle (start -2.54 2.54) (end 2.54 -2.54) (stroke (width 0.25) (type default)) (fill (type none)))'
    pins = []
    pin_items = list(info["pins"].items())
    for index, (number, pin_name) in enumerate(pin_items):
        if len(pin_items) <= 2:
            x = -5.08 if index == 0 else 5.08
            angle = 0 if index == 0 else 180
            y = 0
        else:
            x = -5.08
            y = 2.54 - index * 2.54
            angle = 0
        pins.append(f'(pin passive line (at {x:.2f} {y:.2f} {angle}) (length 2.54) '
                    f'(name {_q(pin_name)} (effects (font (size 1 1)))) (number {_q(number)} (effects (font (size 1 1)))))')
    props = (f'(property "Reference" "U" (at 0 4.5 0) {_effects()}) '
             f'(property "Value" {_q(label)} (at 0 -4.5 0) {_effects()}) '
             f'(property "Footprint" "" (at 0 0 0) {_effects(hidden=True)}) '
             f'(property "Datasheet" "" (at 0 0 0) {_effects(hidden=True)})')
    return (f'(symbol {_q(symbol_id)} (pin_names (offset 0.5)) (exclude_from_sim no) (in_bom yes) (on_board yes) {props} '
            f'(symbol {_q(name + "_0_1")} {graphic}) (symbol {_q(name + "_1_1")} {" ".join(pins)}))')


def _symbol_library_path(library):
    candidates = []
    configured = os.environ.get("KICAD_SYMBOL_DIR")
    if configured:
        candidates.append(Path(configured) / f"{library}.kicad_sym")
    cli = find_kicad_cli()
    if cli:
        candidates.append(Path(cli).parent.parent / "share" / "kicad" / "symbols" / f"{library}.kicad_sym")
    for version in ("10.0", "9.0", "8.0"):
        candidates.append(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "KiCad" / version / "share" / "kicad" / "symbols" / f"{library}.kicad_sym")
    return next((path for path in candidates if path.is_file()), None)


def _extract_symbol_definition(source, name):
    start = source.find(f'(symbol "{name}"')
    if start < 0:
        return None
    depth = 0
    quoted = escaped = comment = False
    for index in range(start, len(source)):
        char = source[index]
        if comment:
            if char == "\n":
                comment = False
        elif quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == ";":
            comment = True
        elif char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise ValueError(f"KiCadシンボル定義 '{name}' の閉じ括弧がありません。")


@lru_cache(maxsize=32)
def _resolve_symbol(symbol_id):
    spec = SYMBOLS[symbol_id]
    library, name = symbol_id.split(":", 1)
    path = _symbol_library_path(library) if library != "CircuitStudio" else None
    if path is None:
        geometry = {}
        pins = list(spec["pins"])
        for index, pin in enumerate(pins):
            if len(pins) <= 2:
                geometry[pin] = (-5.08, 0, 0) if index == 0 else (5.08, 0, 180)
            else:
                geometry[pin] = (-5.08, 2.54 - index * 2.54, 0)
        return _lib_symbol(symbol_id), geometry

    if path.stat().st_size > 32_000_000:
        raise ValueError(f"KiCadシンボルライブラリが32 MB上限を超えています: {path}")
    source = path.read_text(encoding="utf-8")
    library_root = require_root(source, "kicad_symbol_lib")
    definition = next((item for item in children(library_root, "symbol") if len(item) > 1 and item[1] == name), None)
    if definition is None:
        raise ValueError(f"KiCad標準ライブラリにシンボルがありません: {symbol_id}")
    raw = _extract_symbol_definition(source, name)
    if raw is None:
        raise ValueError(f"KiCad標準シンボル定義を抽出できません: {symbol_id}")
    raw = raw.replace(f'(symbol "{name}"', f'(symbol "{symbol_id}"', 1)
    geometry = {}
    for unit in children(definition, "symbol"):
        for pin in children(unit, "pin"):
            number, at = children(pin, "number"), children(pin, "at")
            if number and at and len(at[0]) >= 4:
                pin_number = number[0][1]
                value = tuple(float(part) for part in at[0][1:4])
                if pin_number in geometry and geometry[pin_number] != value:
                    raise ValueError(f"複数位置の同一ピンをサポートしていません: {symbol_id}.{pin_number}")
                geometry[pin_number] = value
    if set(geometry) != set(spec["pins"]):
        raise ValueError(f"KiCad標準シンボルのピン番号がカタログと一致しません: {symbol_id}")
    return raw, geometry


def _positions(data, geometries):
    if len(data["components"]) > 15:
        raise ValueError("現行の単一シート配置上限は15部品です。")
    positions = {}
    directions = {}
    component_positions = {}
    for index, component in enumerate(data["components"]):
        placement = component.get("placement", {})
        if placement.get("rotation_deg", 0) % 360:
            raise ValueError(f"回路図シンボルの回転は未対応です: {component['ref']}")
        if placement.get("side", "top") != "top":
            raise ValueError(f"回路図シンボルの面指定は未対応です: {component['ref']}")
        x = placement.get("x_mm", 80 + (index % 3) * 100)
        y = placement.get("y_mm", 55 + (index // 3) * 47)
        x = round(round(x / 1.27) * 1.27, 3)
        y = round(round(y / 1.27) * 1.27, 3)
        component_positions[component["ref"]] = (x, y)
        for pin, (dx, library_y, library_angle) in geometries[component["symbol"]].items():
            positions[(component["ref"], pin)] = (round(x + dx, 3), round(y - library_y, 3))
            directions[(component["ref"], pin)] = (-library_angle) % 360
    return positions, component_positions, directions


def _wires_and_labels(data, positions, directions):
    output = []
    for component in data["components"]:
        for pin, name in component["pins"].items():
            x, y = positions[(component["ref"], pin)]
            outward = (directions[(component["ref"], pin)] + 180) % 360
            radians = math.radians(outward)
            end_x = round(x + 2.54 * math.cos(radians), 3)
            end_y = round(y + 2.54 * math.sin(radians), 3)
            output.append(f'(wire (pts (xy {x:.3f} {y:.3f}) (xy {end_x:.3f} {end_y:.3f})) (stroke (width 0) (type default)) (uuid {_id()}))')
            justify = "right bottom" if outward == 180 else "left bottom"
            angle = 180 if outward == 180 else 0
            output.append(f'(label {_q(name)} (at {end_x:.3f} {end_y:.3f} {angle}) {_effects(justify)} (uuid {_id()}))')
    return output


def validate_schematic(data, text):
    root = require_root(text, "kicad_sch")
    libraries = children(root, "lib_symbols")
    if len(libraries) != 1:
        raise ValueError("回路図に埋め込みライブラリシンボルが1つ必要です。")
    embedded = {symbol[1] for symbol in children(libraries[0], "symbol") if len(symbol) > 1}
    instance_nodes = children(root, "symbol")
    expected = {component["ref"]: component for component in data["components"]}
    refs = {}
    for instance in instance_nodes:
        lib_ids = [item[1] for item in children(instance, "lib_id") if len(item) > 1]
        if len(lib_ids) != 1 or lib_ids[0] not in embedded:
            raise ValueError("回路図インスタンスが埋め込みシンボルを参照していません。")
        properties = {p[1]: p[2] for p in children(instance, "property") if len(p) > 2}
        ref = properties.get("Reference")
        if ref not in expected or ref in refs:
            raise ValueError("回路図の参照番号がDSL部品表と一致しません。")
        refs[ref] = instance
        if set(p[1] for p in children(instance, "pin") if len(p) > 1) != set(SYMBOLS[expected[ref]["symbol"]]["pins"]):
            raise ValueError(f"{ref} のKiCadピンIDがカタログと一致しません。")
    if set(refs) != set(expected):
        raise ValueError("回路図の部品集合がDSLと一致しません。")
    geometries = {symbol: _resolve_symbol(symbol)[1] for symbol in {c["symbol"] for c in data["components"]}}
    positions, _, _ = _positions(data, geometries)
    parent = {}

    def find(point):
        parent.setdefault(point, point)
        if parent[point] != point:
            parent[point] = find(parent[point])
        return parent[point]

    def union(a, b):
        parent[find(a)] = find(b)

    for wire in children(root, "wire"):
        point_lists = children(wire, "pts")
        if not point_lists:
            continue
        points = [(float(xy[1]), float(xy[2])) for xy in children(point_lists[0], "xy") if len(xy) >= 3]
        for a, b in zip(points, points[1:]):
            union(a, b)
    labels = {(label[1], (float(at[0][1]), float(at[0][2]))) for label in children(root, "label")
              if len(label) > 1 and (at := children(label, "at")) and len(at[0]) >= 3}
    by_net = {}
    for component in data["components"]:
        for pin, net in component["pins"].items():
            by_net.setdefault(net, []).append(positions[(component["ref"], pin)])
    labels_by_root = {}
    for name, point in labels:
        labels_by_root.setdefault(find(point), set()).add(name)
    for net, points in by_net.items():
        if any(net not in labels_by_root.get(find(point), set()) for point in points):
            raise ValueError(f"{net} のピン配線に対応するネットラベルがありません。")
    if any(len(names) > 1 for names in labels_by_root.values()):
        raise ValueError("異なるネット名が同じ配線上で短絡しています。")
    expected_nc = {(component["ref"], pin, positions[(component["ref"], pin)])
                   for component in data["components"] for pin in component.get("no_connect", [])}
    actual_points = {(float(at[0][1]), float(at[0][2])) for marker in children(root, "no_connect")
                     if (at := children(marker, "at")) and len(at[0]) >= 3}
    if {point for _, _, point in expected_nc} != actual_points:
        raise ValueError("明示されたno_connectマーカーがDSLと一致しません。")
    return True


def generate_schematic(data):
    root_id = _id()
    symbol_ids = sorted({c["symbol"] for c in data["components"]})
    resolved = {symbol: _resolve_symbol(symbol) for symbol in symbol_ids}
    geometries = {symbol: value[1] for symbol, value in resolved.items()}
    positions, component_positions, directions = _positions(data, geometries)
    symbols = "\n".join(resolved[symbol][0] for symbol in symbol_ids)
    project_name = data["project"]["name"]
    body = [
        f'(kicad_sch (version {FORMAT_VERSION}) (generator "circuitstudio_ai") (uuid {root_id})',
        '(paper "A3")',
        f'(title_block (title {_q(project_name)}) (rev "0.1") (comment 1 {_q("Generated by CircuitStudio AI; verify before use")}))',
        f'(lib_symbols {symbols})',
    ]
    body.extend(_wires_and_labels(data, positions, directions))
    for component in data["components"]:
        ref, value, symbol_id = component["ref"], component["value"], component["symbol"]
        x, y = component_positions[ref]
        instance_id = _id()
        footprint = component.get("footprint", "")
        body.append(
            f'(symbol (lib_id {_q(symbol_id)}) (at {x:.3f} {y:.3f} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {instance_id}) '
            f'(property "Reference" {_q(ref)} (at {x:.3f} {y-6.35:.3f} 0) {_effects()}) '
            f'(property "Value" {_q(value)} (at {x:.3f} {y+6.35:.3f} 0) {_effects()}) '
            f'(property "Footprint" {_q(footprint)} (at {x:.3f} {y:.3f} 0) {_effects(hidden=True)}) '
            f'(property "Datasheet" {_q(component.get("datasheet", ""))} (at {x:.3f} {y:.3f} 0) {_effects(hidden=True)}) '
            + " ".join(f'(pin {_q(pin)} (uuid {_id()}))' for pin in SYMBOLS[symbol_id]["pins"])
            + f' (instances (project {_q(project_name)} (path {_q("/" + root_id)} (reference {_q(ref)}) (unit 1)))))'
        )
        info = SYMBOLS[symbol_id]
        nc_pins = set(component.get("no_connect", []))
        for pin in info["pins"]:
            if pin in nc_pins:
                px, py = positions[(ref, pin)]
                body.append(f'(no_connect (at {px:.3f} {py:.3f}) (uuid {_id()}))')
    body.append(f'(sheet_instances (path "/" (page "1")))')
    body.append(')')
    text = "\n".join(body) + "\n"
    validate_schematic(data, text)
    return text


def generate_preview(data):
    components = data["components"]
    width = 840
    height = max(340, 170 + ((len(components) + 2) // 3) * 110)
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#101821"/>',
             '<text x="24" y="30" fill="#f2f4f7" font-family="sans-serif" font-size="18">CircuitStudio AI — structural preview</text>']
    for i, comp in enumerate(components):
        x, y = 130 + (i % 3) * 255, 100 + (i // 3) * 110
        lines.append(f'<rect x="{x-35}" y="{y-24}" width="70" height="48" rx="5" fill="#192b39" stroke="#71d6c5"/>')
        lines.append(f'<text x="{x}" y="{y-4}" fill="#f2f4f7" text-anchor="middle" font-family="sans-serif" font-size="13">{html.escape(comp["ref"])}</text>')
        lines.append(f'<text x="{x}" y="{y+13}" fill="#a9bac8" text-anchor="middle" font-family="sans-serif" font-size="11">{html.escape(comp["value"])}</text>')
        pins = list(SYMBOLS[comp["symbol"]]["pins"])
        for j, pin in enumerate(pins):
            if pin not in comp["pins"]:
                continue
            left = len(pins) > 2 or j == 0
            px, py = (x - 35 if left else x + 35), y if len(pins) <= 2 else y + 10 - j * 10
            end_x = px - 12 if left else px + 12
            net = html.escape(comp["pins"][pin])
            lines.append(f'<circle cx="{px}" cy="{py}" r="3" fill="#f2f4f7"/>')
            lines.append(f'<path d="M {px} {py} H {end_x}" stroke="#71d6c5" fill="none" stroke-width="2"/>')
            anchor, side = (end_x - 2, "end") if left else (end_x + 2, "start")
            lines.append(f'<text x="{anchor}" y="{py-4}" fill="#71d6c5" text-anchor="{side}" font-family="sans-serif" font-size="10">{net}</text>')
    lines.append(f'<text x="24" y="{height-18}" fill="#f4c16e" font-family="sans-serif" font-size="12">Preview is structural only; KiCad ERC/DRC and electrical safety are separate checks.</text></svg>')
    return "\n".join(lines) + "\n"


def find_kicad_cli():
    configured = os.environ.get("KICAD_CLI")
    candidates = [configured, shutil.which("kicad-cli")]
    if os.name == "nt":
        try:
            import winreg
            uninstall = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
            for hive, key_path in ((winreg.HKEY_LOCAL_MACHINE, uninstall),
                                   (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                                   (winreg.HKEY_CURRENT_USER, uninstall)):
                try:
                    with winreg.OpenKey(hive, key_path) as root:
                        for index in range(winreg.QueryInfoKey(root)[0]):
                            try:
                                subkey_name = winreg.EnumKey(root, index)
                                with winreg.OpenKey(root, subkey_name) as entry:
                                    display = winreg.QueryValueEx(entry, "DisplayName")[0]
                                    install = winreg.QueryValueEx(entry, "InstallLocation")[0]
                                if "kicad" in display.casefold() and install:
                                    candidates.append(str(Path(install) / "bin" / "kicad-cli.exe"))
                            except OSError:
                                continue
                except OSError:
                    continue
        except ImportError:
            pass
    for version in ("10.0", "9.0", "8.0"):
        candidates.append(str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "KiCad" / version / "bin" / "kicad-cli.exe"))
        candidates.append(str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "KiCad" / version / "bin" / "kicad-cli"))
    return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)


def run_native_check(kind, file_path, output_path=None, timeout=90):
    cli = find_kicad_cli()
    if not cli:
        return {"status": "NOT_EXECUTED", "reason": "kicad-cli が見つかりません。", "command": None}
    if kind not in {"erc", "drc", "svg", "netlist"}:
        raise ValueError("Unsupported KiCad CLI check")
    source = Path(file_path).resolve(strict=True)
    args = [cli]
    if kind == "erc":
        args += ["sch", "erc", "--format", "json"]
    elif kind == "drc":
        args += ["pcb", "drc", "--format", "json"]
    elif kind == "svg":
        args += ["sch", "export", "svg"]
    else:
        args += ["sch", "export", "netlist", "--format", "kicadxml"]
    with tempfile.TemporaryDirectory(prefix="circuitstudio-") as temp:
        work_dir = Path(temp)
        candidates = [source]
        if source.suffix.lower() == ".kicad_sch":
            candidates.extend(source.parent.glob("*.kicad_sch"))
        for suffix in (".kicad_pro", ".kicad_dru"):
            companion = source.with_suffix(suffix)
            if companion.is_file():
                candidates.append(companion)
        unique = list(dict.fromkeys(candidates))
        if len(unique) > 128 or sum(path.stat().st_size for path in unique) > 128_000_000:
            return {"status": "NOT_EXECUTED", "reason": "KiCad検証用の隔離コピーが128ファイル/128 MB上限を超えました。", "command": args}
        for path in unique:
            shutil.copyfile(path, work_dir / path.name)
        source = work_dir / source.name
        out = Path(output_path).resolve() if output_path else Path(temp) / ("report.json" if kind in {"erc", "drc"} else ("out" if kind == "svg" else "netlist.xml"))
        if kind in {"erc", "drc"}:
            args += ["--output", str(out), "--severity-all"]
        else:
            args += ["--output", str(out)]
        args.append(str(source))
        try:
            if output_path and out.exists() and (not out.is_dir() or any(out.iterdir())):
                return {"status": "FAIL", "reason": "既存の出力を上書きしないため処理を停止しました。", "command": args}
            if kind == "svg":
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(args, capture_output=True, timeout=timeout, check=False, shell=False)
            stdout = result.stdout.decode("utf-8", errors="replace")[-4000:]
            stderr = result.stderr.decode("utf-8", errors="replace")[-4000:]
            report, report_error = "", None
            if out.is_file():
                if out.stat().st_size > 32_000_000:
                    report_error = "KiCadレポートが32 MB上限を超えました。"
                else:
                    report = out.read_text(encoding="utf-8", errors="replace")
            violations = []
            counts = {"error": 0, "warning": 0, "exclusion": 0}
            if kind in {"erc", "drc"} and report:
                try:
                    parsed = json.loads(report)
                    def collect(value):
                        if isinstance(value, dict):
                            if value.get("severity") in counts:
                                violations.append(value)
                            for child in value.values():
                                collect(child)
                        elif isinstance(value, list):
                            for child in value:
                                collect(child)
                    collect(parsed)
                    for violation in violations:
                        counts[violation["severity"]] += 1
                except (json.JSONDecodeError, TypeError) as exc:
                    report_error = f"KiCad JSONレポートを解析できません: {exc}"
            artifacts_ok = out.is_dir() and any(out.glob("*.svg")) if kind == "svg" else out.is_file()
            if result.returncode != 0 or report_error or not artifacts_ok:
                status = "FAIL"
            elif counts["error"]:
                status = "FAIL"
            elif counts["warning"] or counts["exclusion"]:
                status = "WARNING"
            else:
                status = "PASS"
            return {"status": status, "returncode": result.returncode, "command": args, "stdout": stdout,
                    "stderr": stderr, "report": report, "report_path": str(out) if output_path else None,
                    "violation_counts": counts, "violation_total": len(violations), "report_error": report_error,
                    "artifact_created": artifacts_ok}
        except subprocess.TimeoutExpired:
            return {"status": "NOT_EXECUTED", "reason": f"KiCad CLI timeout ({timeout}s)", "command": args}
        except OSError as exc:
            return {"status": "NOT_EXECUTED", "reason": str(exc), "command": args}


def _report_markdown(data, diagnostics, native, exports=None):
    exports = exports or {}
    pcb = exports.get("pcb", {})
    rows = ["# CircuitStudio AI — 検証レポート", "", f"- プロジェクト: {data['project']['name']}",
            f"- 設計意図: {data['design']['intent']}", "- 判定: 電気安全/製造適合の承認は未実施", f"- KiCad ERC: {native['status']}",
            f"- KiCadネットリスト: {exports.get('netlist', {}).get('status', 'NOT_EXECUTED')}",
            f"- KiCad SVG: {exports.get('svg', {}).get('status', 'NOT_EXECUTED')}",
            f"- SPICE: {exports.get('spice', {}).get('status', 'NOT_EXECUTED')}",
            f"- PCB生成: {pcb.get('status', 'NOT_EXECUTED')}",
            f"- PCB DRC: {pcb.get('native_drc', {}).get('status', 'NOT_EXECUTED')}",
            f"- 製造判定: {pcb.get('manufacturing_status', 'NOT_PROVEN')}", "",
            "## 診断", "", "| 状態 | 重大度 | 検査ID | 対象 | 根拠 | 推奨 |", "|---|---|---|---|---|---|"]
    for d in diagnostics:
        rows.append(f"| {d.status} | {d.severity} | {d.id} | {', '.join(d.target)} | {d.evidence.replace('|', '/')} | {d.recommendation.replace('|', '/') } |")
    if native["status"] == "NOT_EXECUTED":
        rows.extend(["", f"KiCad ERCは実行していません: {native['reason']}"])
    elif native.get("violation_total", 0):
        rows.extend(["", f"KiCad ERC検出数: {native['violation_counts']} (合計 {native['violation_total']})"])
    if pcb.get("native_drc", {}).get("violation_total"):
        rows.extend(["", f"PCB DRC検出数: {pcb['native_drc'].get('violation_counts')} (合計 {pcb['native_drc']['violation_total']})"])
    if pcb.get("unrouted_nets"):
        rows.extend(["", "未配線ネット: " + ", ".join(pcb["unrouted_nets"])])
    rows.extend(["", "## 制限", "", "電気診断は明示されたDSL値に対する保守的な検査です。実機、安全動作領域、熱、EMC、電流容量、製造可能性を保証しません。"])
    return "\n".join(rows) + "\n"


def compile_project(data, output_root):
    diagnostics, graph = analyze(data)
    root = Path(output_root).expanduser().resolve()
    project_dir = root / safe_project_stem(data["project"]["name"])
    if project_dir.exists() and any(project_dir.iterdir()):
        raise FileExistsError(f"既存ファイルを保持するため空でない出力先は使えません: {project_dir}")
    project_dir.mkdir(parents=True, exist_ok=True)
    blocked = any(d.status == "FAIL" for d in diagnostics)
    source_name = project_dir.name
    source_file = project_dir / f"{source_name}.circuit.yaml"
    source_file.write_text(circuit_json(data), encoding="utf-8")
    native = {"status": "NOT_EXECUTED", "reason": "意味解析に失敗したためERCを実行しませんでした。", "command": None}
    native_pcb = {"status": "NOT_EXECUTED", "reason": "CircuitDSLにPCB仕様がないため未実行です。"}
    native_spice = {"status": "NOT_EXECUTED", "reason": "CircuitDSLにsimulation要求がありません。"}
    outputs = [str(source_file)]
    if not blocked:
        sch = project_dir / f"{source_name}.kicad_sch"
        sch.write_text(generate_schematic(data), encoding="utf-8")
        (project_dir / f"{source_name}.kicad_pro").write_text(json.dumps({"meta": {"version": 1}}, indent=2) + "\n", encoding="utf-8")
        (project_dir / "preview.svg").write_text(generate_preview(data), encoding="utf-8")
        with (project_dir / "BOM.csv").open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Reference", "Value", "Symbol", "Footprint", "Part Number"])
            for c in data["components"]:
                writer.writerow([c["ref"], c["value"], c["symbol"], c.get("footprint", ""), c.get("part_number", "")])
        native = run_native_check("erc", sch)
        native_netlist = run_native_check("netlist", sch, project_dir / f"{source_name}-netlist.xml")
        native_svg = run_native_check("svg", sch, project_dir / "kicad-svg")
        outputs += [str(sch), str(project_dir / f"{source_name}.kicad_pro"), str(project_dir / "preview.svg"), str(project_dir / "BOM.csv")]
        if native_netlist.get("artifact_created"):
            outputs.append(str(project_dir / f"{source_name}-netlist.xml"))
        if native_svg.get("artifact_created"):
            outputs.extend(str(path) for path in (project_dir / "kicad-svg").glob("*.svg"))
        if data.get("simulation"):
            from .spice import generate_spice_deck
            try:
                spice_deck = generate_spice_deck(data)
            except ValueError as exc:
                native_spice = {"status": "BLOCKED", "reason": str(exc)}
            else:
                spice_file = project_dir / f"{source_name}.cir"
                spice_file.write_text(spice_deck, encoding="utf-8")
                native_spice = {"status": "NOT_EXECUTED", "reason": "デッキを生成しました。GUIから実行するか、信頼できるngspice環境を設定してください。",
                                "file": str(spice_file), "models": "ideal R/C and PULSE source"}
                outputs.append(str(spice_file))
        if data.get("pcb"):
            from .pcbgen import generate_pcb
            native_pcb = generate_pcb(data, project_dir / f"{source_name}.kicad_pcb")
            (project_dir / "pcb_diagnostics.json").write_text(json.dumps(native_pcb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if native_pcb.get("file") and Path(native_pcb["file"]).is_file():
                outputs.append(native_pcb["file"])
            outputs.append(str(project_dir / "pcb_diagnostics.json"))
    else:
        native_spice = {"status": "NOT_EXECUTED", "reason": "意味解析に失敗したため実行しませんでした。"}
        native_netlist = {"status": "NOT_EXECUTED", "reason": "意味解析に失敗したため実行しませんでした。"}
        native_svg = {"status": "NOT_EXECUTED", "reason": "意味解析に失敗したため実行しませんでした。"}
    result = {"project": data["project"]["name"], "status": "BLOCKED" if blocked else "STRUCTURE_READY_ELECTRICAL_REVIEW_REQUIRED",
              "electrical_approval": "NOT_PROVEN", "native_erc": native,
              "native_exports": {"netlist": native_netlist, "svg": native_svg, "pcb": native_pcb, "spice": native_spice}, "diagnostics": [d.to_dict() for d in diagnostics],
              "net_graph": graph, "outputs": outputs}
    (project_dir / "diagnostics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (project_dir / "report_ja.md").write_text(_report_markdown(data, diagnostics, native, result["native_exports"]), encoding="utf-8")
    return result
