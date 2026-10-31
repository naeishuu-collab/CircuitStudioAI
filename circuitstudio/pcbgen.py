"""Limited KiCad 10 PCB generation using its bundled pcbnew Python runtime."""

import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

from .analysis import analyze
from .dsl import validate_schema
from .kicad import find_kicad_cli, run_native_check


def find_kicad_python():
    cli = find_kicad_cli()
    if not cli:
        return None
    configured = os.environ.get("KICAD_PYTHON")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file() and _pcbnew_runtime_matches(candidate, cli):
            return candidate
        if platform.system() != "Windows":
            return None
    if platform.system() != "Windows":
        return None
    candidate = Path(cli).with_name("python.exe")
    return candidate if candidate.is_file() else None


def _pcbnew_runtime_matches(python, cli):
    try:
        runtime = subprocess.run(
            [str(python), "-c", "import pcbnew; print(pcbnew.GetBuildVersion())"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15, check=False, shell=False,
        )
        native = subprocess.run(
            [str(cli), "version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15, check=False, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return (runtime.returncode == 0 and native.returncode == 0
            and runtime.stdout.strip() == native.stdout.strip())


def generate_pcb(data, output_path, timeout=120):
    """Generate explicit board geometry/routes; never infer footprints or auto-route."""
    validate_schema(data)
    output = Path(output_path).expanduser().resolve()
    if output.suffix.lower() != ".kicad_pcb":
        raise ValueError("PCB出力ファイルは .kicad_pcb で指定してください。")
    if output.exists():
        return {"status": "BLOCKED", "reason": "既存PCBを上書きしないため生成を停止しました。", "file": str(output)}
    if not data.get("pcb"):
        return {"status": "BLOCKED", "reason": "CircuitDSL v2のpcb仕様がありません。"}
    board = data["pcb"]
    constraints = board.get("constraints", {})
    if board.get("layers") != 2 or board.get("board_thickness_mm") is None or not board.get("outline"):
        return {"status": "BLOCKED", "reason": "PCB生成には明示した2層、board_thickness_mm、矩形外形が必要です。"}
    if any(not isinstance(constraints.get(key), (int, float)) or isinstance(constraints.get(key), bool) or constraints[key] <= 0
           for key in ("clearance_mm", "trace_width_mm")):
        return {"status": "BLOCKED", "reason": "PCB生成には正のclearance_mmとtrace_width_mm制約が必要です。"}
    if board.get("mounting_holes"):
        return {"status": "BLOCKED", "reason": "取付穴の生成は未対応です。入力を無視せず基板生成を止めました。"}
    placements = {item["ref"]: item for item in board.get("placements", [])}
    if set(placements) != {item["ref"] for item in data["components"]}:
        return {"status": "BLOCKED", "reason": "全部品のPCB配置を明示してください。"}
    if any(not component.get("footprint") for component in data["components"]):
        return {"status": "BLOCKED", "reason": "全コンポーネントの標準ライブラリフットプリントを指定してください。"}
    if any(item.get("side", "top") != "top" for item in placements.values()):
        return {"status": "BLOCKED", "reason": "裏面フットプリント配置は未対応です。"}
    failures = [item for item in analyze(data)[0] if item.status == "FAIL"]
    if failures:
        return {"status": "BLOCKED", "reason": "CircuitDSLの意味検証にFAILがあります。", "diagnostics": [item.to_dict() for item in failures]}
    python = find_kicad_python()
    if not python:
        return {"status": "NOT_EXECUTED",
                "reason": "KiCadと同じバージョンのpcbnew Pythonが未検出です。macOSではABI確認済みの実行環境をKICAD_PYTHONに指定してください。",
                "file": str(output)}
    adapter = Path(__file__).with_name("pcbnew_adapter.py")
    with tempfile.TemporaryDirectory(prefix="circuitstudio-pcb-") as temp:
        source = Path(temp) / "circuit.json"
        source.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        command = [str(python), str(adapter), str(source), str(output)]
        try:
            result = subprocess.run(command, capture_output=True, timeout=timeout, check=False, shell=False)
        except subprocess.TimeoutExpired:
            return {"status": "NOT_EXECUTED", "reason": f"KiCad pcbnew timeout ({timeout}s)", "command": command,
                    "file": str(output)}
        except OSError as exc:
            return {"status": "NOT_EXECUTED", "reason": str(exc), "command": command, "file": str(output)}
        stdout = result.stdout.decode("utf-8", errors="replace")[-4000:]
        stderr = result.stderr.decode("utf-8", errors="replace")[-4000:]
        if result.returncode != 0:
            return {"status": "FAIL", "reason": stderr.strip() or "KiCad pcbnewが基板を生成できませんでした。",
                    "returncode": result.returncode, "command": command, "stdout": stdout, "stderr": stderr,
                    "file": str(output), "partial_file_created": output.is_file()}
        try:
            generated = json.loads(stdout)
        except json.JSONDecodeError as exc:
            return {"status": "FAIL", "reason": f"pcbnewアダプターの結果JSONを解析できません: {exc}",
                    "command": command, "stdout": stdout, "file": str(output)}
    if not output.is_file():
        return {"status": "FAIL", "reason": "pcbnewは成功を返しましたがPCBファイルがありません。", "file": str(output)}
    native_drc = run_native_check("drc", output)
    routed = not generated["unrouted_nets"]
    production = "NOT_PROVEN" if routed and native_drc["status"] == "PASS" else "NOT_MANUFACTURABLE"
    return {"status": "ROUTED" if routed else "UNROUTED", "manufacturing_status": production,
            "file": str(output), "pcbnew_version": generated["pcbnew_version"],
            "design_conditions": {"layers": board["layers"], "board_thickness_mm": board["board_thickness_mm"],
                                  "outline": board["outline"], "constraints": constraints},
            "footprints": generated["footprints"], "routes": generated["routes"],
            "unrouted_nets": generated["unrouted_nets"], "native_drc": native_drc,
            "trace_capacity": {"status": "NOT_EXECUTED", "reason": "配線幅だけでは電流容量を評価できません。銅厚、電流、温度条件、層構成と放熱条件が必要です。"}}
