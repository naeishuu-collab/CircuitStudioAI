"""KiCad 10 pcbnew subprocess adapter. Kept isolated from the user's Python runtime."""

import json
import re
import sys
from pathlib import Path

import pcbnew


def _mm(point):
    return pcbnew.VECTOR2I(pcbnew.FromMM(point[0]), pcbnew.FromMM(point[1]))


def _inside(point, bounds):
    x, y = point
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


def build(data, output):
    if pcbnew.GetBuildVersion().split(".")[0] != "10":
        raise ValueError(f"KiCad 10用アダプターですが、pcbnewは{pcbnew.GetBuildVersion()}です。")
    board_spec = data.get("pcb", {})
    if board_spec.get("layers") != 2:
        raise ValueError("現在のPCB生成は2層基板のみ対応します。")
    if board_spec.get("mounting_holes"):
        raise ValueError("取付穴のPCB生成は未対応です。穴位置を無視せず生成を停止しました。")
    if Path(output).exists():
        raise FileExistsError(f"既存PCBを上書きしません: {output}")
    cli = Path(sys.executable).resolve()
    footprint_root = cli.parent.parent / "share" / "kicad" / "footprints"
    if not footprint_root.is_dir():
        raise FileNotFoundError(f"KiCadフットプリントライブラリがありません: {footprint_root}")
    outline = board_spec.get("outline") or {}
    constraints = board_spec.get("constraints") or {}
    thickness = board_spec.get("board_thickness_mm")
    width, height = outline.get("width_mm"), outline.get("height_mm")
    x0, y0 = outline.get("origin_x_mm", 0), outline.get("origin_y_mm", 0)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (width, height, x0, y0, thickness)):
        raise ValueError("PCB外形とboard_thickness_mmを明示してください。")
    if width <= 0 or height <= 0:
        raise ValueError("PCB外形の幅と高さは正の値が必要です。")
    clearance = constraints.get("clearance_mm")
    track_width = constraints.get("trace_width_mm")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 for v in (clearance, track_width)):
        raise ValueError("PCB生成には正のclearance_mmとtrace_width_mm制約が必要です。")
    bounds = (x0, y0, x0 + width, y0 + height)
    placements = {item["ref"]: item for item in board_spec.get("placements", [])}
    refs = {item["ref"] for item in data["components"]}
    if set(placements) != refs:
        missing, extra = refs - set(placements), set(placements) - refs
        raise ValueError(f"全部品のPCB配置を一意に指定してください。未配置={sorted(missing)} 不明={sorted(extra)}")

    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    settings = board.GetDesignSettings()
    settings.m_MinClearance = pcbnew.FromMM(clearance)
    settings.m_CopperEdgeClearance = pcbnew.FromMM(clearance)
    settings.m_TrackMinWidth = pcbnew.FromMM(track_width)
    settings.SetBoardThickness(pcbnew.FromMM(thickness))
    nets = {}
    for spec in data["nets"]:
        net = pcbnew.NETINFO_ITEM(board, spec["name"])
        board.Add(net)
        nets[spec["name"]] = net

    pads_by_component = {}
    pad_positions_by_net = {}
    for component in data["components"]:
        footprint_id = component.get("footprint", "")
        if not isinstance(footprint_id, str) or footprint_id.count(":") != 1:
            raise ValueError(f"{component['ref']} に明示的な Library:Footprint が必要です。")
        library, name = footprint_id.split(":", 1)
        if not re.fullmatch(r"[A-Za-z0-9_.+-]+", library) or not re.fullmatch(r"[A-Za-z0-9_.+-]+", name) or ".." in library or ".." in name:
            raise ValueError(f"フットプリント識別子が不正です: {footprint_id}")
        lib_path = (footprint_root / f"{library}.pretty").resolve(strict=True)
        if not lib_path.is_relative_to(footprint_root.resolve()):
            raise ValueError("フットプリント参照が標準ライブラリ範囲外です。")
        footprint = pcbnew.FootprintLoad(str(lib_path), name)
        if footprint is None:
            raise ValueError(f"KiCadにフットプリントがありません: {footprint_id}")
        placement = placements[component["ref"]]
        if placement.get("side", "top") != "top":
            raise ValueError(f"裏面配置は未対応です: {component['ref']}")
        anchor = (float(placement["x_mm"]), float(placement["y_mm"]))
        if not _inside(anchor, bounds):
            raise ValueError(f"{component['ref']} の配置原点が基板外形の外です。")
        footprint.SetPosition(_mm(anchor))
        footprint.SetOrientationDegrees(float(placement.get("rotation_deg", 0)))
        footprint.SetReference(component["ref"])
        footprint.SetValue(component["value"])
        board.Add(footprint)
        pads = {}
        for pad in footprint.Pads():
            number = pad.GetNumber()
            if number in pads:
                raise ValueError(f"{component['ref']} のフットプリントに重複パッド番号 {number} があります。")
            pads[number] = pad
        required = set(component.get("pins", {})) | set(component.get("no_connect", []))
        if set(pads) != required:
            raise ValueError(f"{component['ref']}のシンボル/フットプリントパッドが一致しません。symbol={sorted(required)} footprint={sorted(pads)}")
        pads_by_component[component["ref"]] = pads
        for pin, net_name in component.get("pins", {}).items():
            if net_name not in nets:
                raise ValueError(f"{component['ref']}.{pin} のネット '{net_name}' は未定義です。")
            pad = pads[pin]
            pad.SetNet(nets[net_name])
            pos = pad.GetPosition()
            pad_positions_by_net.setdefault(net_name, []).append((pos.x, pos.y))

    edge = pcbnew.PCB_SHAPE()
    edge.SetShape(pcbnew.SHAPE_T_RECT)
    edge.SetStart(_mm((x0, y0)))
    edge.SetEnd(_mm((x0 + width, y0 + height)))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(pcbnew.FromMM(0.05))
    board.Add(edge)

    route_edges = {}
    for route in board_spec.get("routes", []):
        net_name = route["net"]
        if net_name not in nets:
            raise ValueError(f"配線が未定義ネットを参照しています: {net_name}")
        line_width = route.get("width_mm", track_width)
        if line_width < track_width:
            raise ValueError(f"{net_name}の配線幅が指定した最小幅を下回ります。")
        points = [(float(p["x_mm"]), float(p["y_mm"])) for p in route["points"]]
        if any(not _inside(point, bounds) for point in points):
            raise ValueError(f"{net_name}の配線が基板外形をはみ出しています。")
        native_points = [_mm(point) for point in points]
        route_edges.setdefault(net_name, []).extend((a.x, a.y, b.x, b.y) for a, b in zip(native_points, native_points[1:]))
        layer = pcbnew.F_Cu if route["layer"] == "F.Cu" else pcbnew.B_Cu
        for start, end in zip(native_points, native_points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(start)
            track.SetEnd(end)
            track.SetWidth(pcbnew.FromMM(line_width))
            track.SetLayer(layer)
            track.SetNet(nets[net_name])
            board.Add(track)

    unrouted = []
    for net_name, terminals in pad_positions_by_net.items():
        if len(terminals) < 2:
            continue
        parent = {}

        def find(point):
            parent.setdefault(point, point)
            if parent[point] != point:
                parent[point] = find(parent[point])
            return parent[point]

        edges = route_edges.get(net_name, [])
        route_vertices = {(x1, y1) for x1, y1, _, _ in edges} | {(x2, y2) for _, _, x2, y2 in edges}
        for x1, y1, x2, y2 in edges:
            parent[find((x1, y1))] = find((x2, y2))
        roots = {find(point) for point in terminals}
        if len(roots) != 1 or not set(terminals) <= route_vertices:
            unrouted.append(net_name)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    if not pcbnew.SaveBoard(str(output), board):
        raise OSError(f"pcbnewで基板を保存できません: {output}")
    return {"pcbnew_version": pcbnew.GetBuildVersion(), "footprints": len(pads_by_component),
            "routes": sum(len(edges) for edges in route_edges.values()), "unrouted_nets": sorted(unrouted)}


def main():
    source, output = map(Path, sys.argv[1:3])
    data = json.loads(source.read_text(encoding="utf-8"))
    result = build(data, output)
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
