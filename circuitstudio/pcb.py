"""Read-only KiCad board inspection. DRC is authoritative only when KiCad CLI runs."""

import re
from pathlib import Path

from .analysis import issue
from .kicad import run_native_check
from .sexpr import SExprError, children, require_root

MAX_BOARD_BYTES = 64_000_000


def inspect_board(path):
    source = Path(path).resolve(strict=True)
    if source.suffix.lower() != ".kicad_pcb":
        raise ValueError("拡張子 .kicad_pcb のファイルを選択してください。")
    if source.stat().st_size > MAX_BOARD_BYTES:
        raise ValueError("PCBファイルが64 MB上限を超えています。")
    text = source.read_text(encoding="utf-8-sig", errors="strict")
    try:
        root = require_root(text, "kicad_pcb")
    except SExprError as exc:
        raise ValueError(f"KiCad PCB S式が不正です: {exc}") from exc
    edge_objects = {"gr_line", "gr_rect", "gr_poly", "gr_arc", "gr_circle"}
    has_outline = any(any(isinstance(layer, list) and len(layer) > 1 and layer[1] == "Edge.Cuts"
                          for layer in children(item, "layer"))
                      for item in root if isinstance(item, list) and item and item[0] in edge_objects)
    counts = {"footprints": len(children(root, "footprint")), "segments": len(children(root, "segment")),
              "vias": len(children(root, "via")), "zones": len(children(root, "zone")),
              "nets": len(children(root, "net")), "edge_cuts": has_outline}
    native = run_native_check("drc", source)
    diagnostics = []
    if not counts["edge_cuts"]:
        diagnostics.append(issue("PCB_OUTLINE_UNCERTAIN", "UNKNOWN", "warning", "Edge.Cuts層の記述を確認できません。ファイル全体の解析ではありません。",
                                 "基板外形をKiCadで確認し、kicad-cli DRCを実行してください。", "限定的なS式テキスト検出"))
    if not counts["segments"]:
        diagnostics.append(issue("PCB_NO_TRACKS", "UNKNOWN", "warning", "segment記述が0件です。未配線の可能性があります。",
                                 "KiCadの未配線数とラッツネストを確認してください。", "segment表記の件数検出"))
    diagnostics.append(issue("PCB_TRACE_CAPACITY", "NOT_EXECUTED", "info", "電流容量/温度上昇は未評価です。銅厚、幅、層、許容温度、周囲温度が必要です。",
                             "設計条件を入力し、IPC-2152等の適用条件と実装/冷却を確認してください。", "前提条件不足のため計算なし"))
    if native["status"] == "NOT_EXECUTED":
        diagnostics.append(issue("PCB_DRC_NOT_EXECUTED", "NOT_EXECUTED", "info", native["reason"],
                                 "KiCad 10のkicad-cli pcb drcを実行してください。", "公式KiCad CLI DRCが未実行"))
    return {"file": str(source), "status": native["status"], "counts": counts,
            "diagnostics": [d.to_dict() for d in diagnostics], "native_drc": native}
