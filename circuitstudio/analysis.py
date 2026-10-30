"""Semantic, graph and conservative electrical checks for CircuitDSL."""

import re
from dataclasses import asdict, dataclass

from .catalog import SYMBOLS


@dataclass
class Diagnostic:
    id: str
    status: str
    severity: str
    target: list[str]
    evidence: str
    recommendation: str
    method: str

    def to_dict(self):
        return asdict(self)


def issue(code, status, severity, evidence, recommendation, method, target=None):
    return Diagnostic(code, status, severity, target or [], evidence, recommendation, method)


def parse_quantity(value):
    """Convert a scalar with an SI prefix to its base-unit float; unknown units return None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return number if number == number and abs(number) != float("inf") else None
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*(p|n|u|µ|μ|m|k|K|M|G)?\s*(Ohms|Ohm|ohm|Ω|Ω|Hz|A|V|W|F|H|s|mm|mil)?\s*", value)
    if not match:
        return None
    prefixes = {None: 1, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3,
                "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}
    number = float(match.group(1)) * prefixes[match.group(2)]
    return number if number == number and abs(number) != float("inf") else None


def build_net_graph(data):
    graph = {net["name"]: [] for net in data.get("nets", [])}
    for component in data.get("components", []):
        for pin, net in component.get("pins", {}).items():
            graph.setdefault(net, []).append({"ref": component["ref"], "pin": pin})
    return graph


def _hbridge_rules(data):
    if data.get("design", {}).get("architecture") not in {"h_bridge", "discrete_h_bridge"}:
        return []
    out = []
    params = data["design"].get("parameters", {})
    required = {
        "motor_voltage_V": "モーター電圧",
        "motor_continuous_A": "モーター連続電流",
        "motor_stall_A": "モーター停止電流",
        "gate_drive_V": "ゲート駆動電圧",
    }
    missing = [label for name, label in required.items() if parse_quantity(params.get(name)) is None]
    if missing:
        out.append(issue("HBRIDGE_OPERATING_DATA", "UNKNOWN", "critical",
                         "未確定: " + ", ".join(missing) + "。電流定格・発熱・ゲート駆動を判断できません。",
                         "モーターの連続/停止電流、最大電源電圧、実際のゲート駆動条件を測定値またはデータシートで指定してください。",
                         "設計条件と部品データシートの照合"))
    fet_refs = [c["ref"] for c in data.get("components", []) if c.get("symbol") == "CircuitStudio:NMOS_3Pin"]
    if data["design"].get("architecture") == "discrete_h_bridge" and len(fet_refs) != 4:
        out.append(issue("HBRIDGE_SWITCH_COUNT", "FAIL", "error", f"離散MOSFET構成は4スイッチを想定しますが、検出した個数は{len(fet_refs)}です。",
                         "ブリッジ構成を確認し、各FETの高側/低側と端子割当を明示してください。", "回路構成の個数チェック", fet_refs))
    if params.get("dead_time_ns") is None:
        out.append(issue("HBRIDGE_DEAD_TIME", "UNKNOWN", "critical", "デッドタイム条件がありません。上下アーム同時導通の可能性を評価できません。",
                         "ゲートドライバのデータシートとMOSFET切替時間からデッドタイムを設計してください。", "ゲート波形・タイミングの確認", fet_refs))
    if params.get("overcurrent_protection") is not True:
        out.append(issue("HBRIDGE_OVERCURRENT", "UNKNOWN", "critical", "過電流保護が確認できません。停止電流や短絡時の保護を証明できません。",
                         "電流制限/ヒューズと故障時遮断の設計値を追加してください。", "保護回路と停止電流のレビュー", fet_refs))
    for key, code, message, correction in (
        ("high_side_drive_confirmed", "HBRIDGE_HIGH_SIDE_DRIVE", "高側ゲート駆動方式が確定していません。",
         "ハイサイドのゲート電圧/デューティ条件に対応するドライバを指定してください。"),
        ("inductive_transient_protection", "HBRIDGE_TRANSIENT_PROTECTION", "誘導性負荷の過渡保護が確認できません。",
         "循環電流経路、クランプ素子、過渡電圧定格を検証してください。"),
        ("reset_safe_state_confirmed", "HBRIDGE_RESET_STATE", "起動/リセット時の安全状態が確認できません。",
         "RP2040起動中の入力状態とゲートの既定オフを回路とファームウェアで確認してください。"),
    ):
        if params.get(key) is not True:
            out.append(issue(code, "UNKNOWN", "critical", message, correction, "設計条件/データシート/起動波形のレビュー", fet_refs))
    if not any(c.get("symbol") == "Device:C" and {c.get("pins", {}).get("1"), c.get("pins", {}).get("2")} >= {"VM", "GND"}
               for c in data.get("components", [])):
        out.append(issue("HBRIDGE_BULK_CAP", "WARNING", "warning", "VM-GND間のバルクコンデンサがネット接続から確認できません。",
                         "モーター電源の配線インダクタンス、電流リップル、部品のリップル電流定格に基づいて配置してください。",
                         "ネットグラフ確認。近接配置は未検証"))
    return out


RULE_PLUGINS = [_hbridge_rules]


def analyze(data):
    diagnostics = []
    nets = data.get("nets", [])
    components = data.get("components", [])
    for unknown in data.get("design", {}).get("unknowns", []):
        diagnostics.append(issue("DESIGN_ASSUMPTION_UNKNOWN", "UNKNOWN", "warning", f"未確定条件: {unknown}",
                                 "値を確認してDSLに反映してください。", "ユーザー/データシートによる条件確定"))
    net_names = [n["name"] for n in nets]
    if not components:
        diagnostics.append(issue("DSL_EMPTY_CIRCUIT", "FAIL", "error", "components が空です。出力できる回路要素がありません。",
                                 "部品と接続を指定してください。安全条件の不足だけなら design.unknowns に残し、実体の推定はしないでください。", "構造解析"))
    # shortcut: the single-sheet layout fits at most 15 symbols on A3; add pagination when larger designs are required.
    if len(components) > 15:
        diagnostics.append(issue("SCHEMATIC_LAYOUT_LIMIT", "FAIL", "error", f"単一シートの配置上限15部品を超えています: {len(components)}部品。",
                                 "設計を複数の階層シートに分割するか、ページ分割を実装してください。", "固定A3配置容量の確認"))
    seen_nets = set()
    for name in net_names:
        if name in seen_nets:
            diagnostics.append(issue("DSL_DUPLICATE_NET", "FAIL", "error", f"net '{name}' が重複しています。",
                                     "各ネット名を一意にしてください。", "DSLネット表検証", [name]))
        seen_nets.add(name)
    seen_refs = set()
    graph = build_net_graph(data)
    for net in nets:
        if net.get("kind", "signal") in {"power", "ground"} and not graph.get(net["name"]):
            diagnostics.append(issue("POWER_NET_UNUSED", "WARNING", "warning", f"{net.get('kind', 'signal')} net '{net['name']}' に接続部品がありません。",
                                     "電源/GND接続を確認してください。", "ネットグラフ解析", [net["name"]]))
    if data.get("schema_version") == 2:
        known_nets = set(net_names)
        simulation = data.get("simulation")
        if simulation:
            source = simulation.get("source", {})
            referenced = {source.get("positive_net"), source.get("negative_net"), *simulation.get("observe_nets", [])}
            for name in sorted(referenced - known_nets):
                diagnostics.append(issue("SPICE_NET_UNKNOWN", "FAIL", "error", f"SPICE条件が未定義ネット '{name}' を参照しています。",
                                         "simulationで指定したネット名をnetsに宣言してください。", "SPICEネット参照照合", [name]))
            ground_names = {net["name"] for net in nets if net.get("kind") == "ground"}
            if source.get("negative_net") not in ground_names or source.get("positive_net") == source.get("negative_net"):
                diagnostics.append(issue("SPICE_SOURCE_REFERENCE", "FAIL", "error", "SPICE電圧源の負端子はGNDネット、正端子は別ネットである必要があります。",
                                         "source.positive_netとsource.negative_netを確認してください。", "SPICE電源基準の意味検査"))
        for rail in data.get("power_rails", []):
            name = rail["net"]
            if name not in known_nets:
                diagnostics.append(issue("POWER_RAIL_NET_UNKNOWN", "FAIL", "error", f"電源条件が未定義ネット '{name}' を参照しています。",
                                         "power_rails.net と nets.name を一致させてください。", "電源ネット参照照合", [name]))
            nominal = parse_quantity(rail.get("nominal_voltage_V"))
            minimum = parse_quantity(rail.get("min_voltage_V"))
            maximum = parse_quantity(rail.get("max_voltage_V"))
            if minimum is not None and maximum is not None and minimum > maximum:
                diagnostics.append(issue("POWER_RAIL_RANGE", "FAIL", "error", f"{name} の最小電圧が最大電圧を上回っています。",
                                         "最小/最大電圧条件を確認してください。", "単位変換後の範囲比較", [name]))
            if nominal is not None and ((minimum is not None and nominal < minimum) or (maximum is not None and nominal > maximum)):
                diagnostics.append(issue("POWER_RAIL_RANGE", "FAIL", "error", f"{name} の公称電圧 {nominal:g} V が指定範囲外です。",
                                         "公称値と最小/最大電圧の条件を確認してください。", "単位変換後の範囲比較", [name]))
        minimum_width = parse_quantity(data.get("pcb", {}).get("constraints", {}).get("trace_width_mm"))
        outline = data.get("pcb", {}).get("outline", {})
        if outline:
            left, top = outline.get("origin_x_mm", 0), outline.get("origin_y_mm", 0)
            right, bottom = left + outline["width_mm"], top + outline["height_mm"]
        else:
            left = top = right = bottom = None
        for route in data.get("pcb", {}).get("routes", []):
            name = route["net"]
            if name not in known_nets:
                diagnostics.append(issue("PCB_ROUTE_NET_UNKNOWN", "FAIL", "error", f"配線が未定義ネット '{name}' を参照しています。",
                                         "配線ネットを nets.name に宣言してください。", "PCB配線ネット照合", [name]))
            width = route.get("width_mm", minimum_width)
            if minimum_width is not None and width is not None and width < minimum_width:
                diagnostics.append(issue("PCB_TRACE_WIDTH_BELOW_MINIMUM", "FAIL", "error", f"{name} の配線幅 {width:g} mm が最小制約 {minimum_width:g} mm を下回ります。",
                                         "配線幅またはPCB最小幅制約を修正し、DRCを再実行してください。", "DSL配線幅比較", [name]))
            if left is not None and any(not (left <= point["x_mm"] <= right and top <= point["y_mm"] <= bottom) for point in route["points"]):
                diagnostics.append(issue("PCB_ROUTE_OUTSIDE_OUTLINE", "FAIL", "error", f"{name} の配線点が基板外形の範囲外です。",
                                         "配線座標または基板外形を修正してください。", "配線点と矩形外形の比較", [name]))
        component_refs = {component["ref"] for component in components}
        placed = set()
        for placement in data.get("pcb", {}).get("placements", []):
            ref = placement["ref"]
            if ref not in component_refs or ref in placed:
                diagnostics.append(issue("PCB_PLACEMENT_REFERENCE", "FAIL", "error", f"PCB配置参照 '{ref}' が存在しないか重複しています。",
                                         "部品参照を一意に指定してください。", "部品参照番号照合", [ref]))
            placed.add(ref)
        for note in data.get("safety_notes", []):
            diagnostics.append(issue("SAFETY_NOTE_REVIEW", "UNKNOWN", "warning", f"安全上の注意: {note}",
                                     "注意事項を回路図、基板、部品仕様と照合してください。", "設計メモ確認"))
    for component in components:
        ref, symbol = component["ref"], component["symbol"]
        if ref in seen_refs:
            diagnostics.append(issue("DSL_DUPLICATE_REFERENCE", "FAIL", "error", f"参照番号 '{ref}' が重複しています。",
                                     "重複しない参照番号を指定してください。", "DSL部品表検証", [ref]))
        seen_refs.add(ref)
        if not re.fullmatch(r"[A-Za-z]{1,4}\d+[A-Za-z]?", ref):
            diagnostics.append(issue("DSL_INVALID_REFERENCE", "FAIL", "error", f"参照番号 '{ref}' はKiCad形式に適合しません。",
                                     "例: R1, U2, J1 の形式にしてください。", "参照番号形式検査", [ref]))
        spec = SYMBOLS.get(symbol)
        if spec is None:
            diagnostics.append(issue("SYMBOL_UNKNOWN", "FAIL", "error", f"未登録シンボル '{symbol}'。ピン番号は推測しません。",
                                     "catalog.py に仕様がある記号を選ぶか、実際のシンボル/データシート情報を登録してください。", "明示的シンボルカタログ照合", [ref]))
            continue
        mapped = set(component.get("pins", {}))
        ncs = set(component.get("no_connect", []))
        invalid = (mapped | ncs) - set(spec["pins"])
        if invalid:
            diagnostics.append(issue("PIN_UNKNOWN", "FAIL", "error", f"{ref} の '{symbol}' に存在しないピン番号: {', '.join(sorted(invalid))}。",
                                     "シンボル定義のピン番号と照合してください。", "ピンカタログ照合", [ref]))
        overlap = mapped & ncs
        if overlap:
            diagnostics.append(issue("PIN_CONNECTED_AND_NC", "FAIL", "error", f"{ref} のピンが接続とno_connectの両方にあります: {', '.join(sorted(overlap))}。",
                                     "pinを片方の状態にだけ指定してください。", "DSL部品接続検証", [ref]))
        for pin, net in component.get("pins", {}).items():
            if net not in seen_nets:
                diagnostics.append(issue("NET_UNKNOWN", "FAIL", "error", f"{ref}.{pin} が未定義ネット '{net}' を参照しています。",
                                         "nets にネットを宣言するか、参照先を修正してください。", "ネット名解決", [ref, net]))
        dangling = set(spec["pins"]) - mapped - ncs
        if dangling:
            diagnostics.append(issue("PIN_UNSPECIFIED", "UNKNOWN", "warning", f"{ref} のピン {', '.join(sorted(dangling))} が未指定です。",
                                     "意図的な未接続なら no_connect に列挙してください。", "ピン割当表の網羅性確認", [ref]))
        if len(mapped) > 1 and len(set(component["pins"].values())) == 1:
            diagnostics.append(issue("COMPONENT_SELF_SHORT", "FAIL", "critical", f"{ref} の複数端子が同一ネットに接続されています。",
                                     "意図した短絡でない限り、接続ネットを修正してください。", "端子ネット割当比較", [ref]))
        if component.get("part_number"):
            diagnostics.append(issue("PART_PINOUT_UNVERIFIED", "UNKNOWN", "warning",
                                     f"{ref} の型番 {component['part_number']} は標準部品DBにありません。DSLで指定したシンボルとピン割当だけを使用します。",
                                     "メーカーのデータシートと回路図シンボルのピン番号を照合してください。", "部品型番の外部照合は未実施", [ref]))
        _ratings(component, data, diagnostics)
    power_nets = [n for n in nets if n.get("kind", "signal") == "power"]
    ground_nets = [n for n in nets if n.get("kind", "signal") == "ground"]
    power_used = all(graph.get(n["name"]) for n in power_nets)
    ground_used = all(graph.get(n["name"]) for n in ground_nets)
    if not power_nets:
        diagnostics.append(issue("POWER_RAIL_MISSING", "UNKNOWN", "warning", "電源種別のネットが指定されていません。", "入力/出力電圧と電源ネットを定義してください。", "ネット種別の確認"))
    if not ground_nets:
        diagnostics.append(issue("GROUND_MISSING", "FAIL", "error", "GND種別のネットがありません。", "回路の共通基準を指定してください。", "ネット種別の確認"))
    if power_nets and ground_nets and power_used and ground_used:
        diagnostics.append(issue("POWER_GROUND_DECLARED", "PASS", "info", f"電源ネット{len(power_nets)}個、GNDネット{len(ground_nets)}個が部品ピンに割り当てられています。電流ループ/帰路は未証明です。",
                                 "KiCad ERC と実回路の帰路をレビューしてください。", "DSLネット種別と端子割当の検査"))
    elif power_nets and ground_nets:
        diagnostics.append(issue("POWER_GROUND_CONNECTIVITY_UNKNOWN", "UNKNOWN", "warning", "電源/GNDのいずれかが部品ピンに接続されていません。",
                                 "電源/GNDの端子割当と実際の電流帰路を確認してください。", "ネットグラフの端子数確認"))
    for plugin in RULE_PLUGINS:
        diagnostics.extend(plugin(data))
    return diagnostics, graph


def _ratings(component, data, out):
    ratings = component.get("ratings", {})
    params = data.get("design", {}).get("parameters", {})
    symbol = component.get("symbol")
    if symbol == "Device:R":
        current = parse_quantity(params.get("operating_current_A"))
        resistance = parse_quantity(component.get("value"))
        power_rating = parse_quantity(ratings.get("power_W"))
        if current is None or resistance is None or power_rating is None:
            out.append(issue("RESISTOR_POWER_UNKNOWN", "UNKNOWN", "warning", f"{component['ref']} の電流、抵抗値、または定格電力が不足し消費電力を比較できません。",
                             "値と定格を指定し、P=I²R と温度ディレーティングで確認してください。", "SI値変換後に P=I²R", [component["ref"]]))
        else:
            power = current * current * resistance
            out.append(issue("RESISTOR_POWER_RATING", "FAIL" if power > power_rating else "PASS", "error" if power > power_rating else "info",
                             f"推定消費電力 {power:.4g} W、指定定格 {power_rating:.4g} W (P=I²R; 温度ディレーティング未考慮)。",
                             "抵抗値/電流/部品定格を見直し、周囲温度と実装条件で再評価してください。", "定常式 P=I²R", [component["ref"]]))
    if symbol == "Device:C":
        supply = parse_quantity(params.get("motor_voltage_V") or params.get("supply_voltage_V"))
        rating = parse_quantity(ratings.get("voltage_V"))
        if supply is not None and rating is not None:
            out.append(issue("CAPACITOR_VOLTAGE_RATING", "FAIL" if rating < supply else "PASS", "error" if rating < supply else "info",
                             f"供給電圧 {supply:g} V、コンデンサ指定耐圧 {rating:g} V。サージ/温度余裕は別途確認が必要です。",
                             "DCバイアス、リップル、サージを含むデータシート条件を確認してください。", "電圧定格の単純比較", [component["ref"]]))
        else:
            out.append(issue("CAPACITOR_RATING_UNKNOWN", "UNKNOWN", "warning", f"{component['ref']} の回路電圧または耐圧がありません。",
                             "耐圧と実際の過渡電圧を指定してください。", "DSL定格情報の確認", [component["ref"]]))
    if symbol == "CircuitStudio:NMOS_3Pin":
        voltage = parse_quantity(params.get("motor_voltage_V") or params.get("supply_voltage_V"))
        current = parse_quantity(params.get("motor_stall_A") or params.get("operating_current_A"))
        gate = parse_quantity(params.get("gate_drive_V"))
        needs = (("vds_max_V", voltage, "VDS"), ("id_max_A", current, "ID"), ("vgs_max_V", gate, "VGS"))
        for field, required, label in needs:
            rated = parse_quantity(ratings.get(field))
            if required is None or rated is None:
                out.append(issue("MOSFET_RATING_UNKNOWN", "UNKNOWN", "critical", f"{component['ref']} の{label}必要値または定格が不明です。",
                                 "ゲートドライバ過渡、停止電流、温度ディレーティングを含むデータシート値を指定してください。", "指定電圧/電流と部品絶対最大定格の比較", [component["ref"]]))
            else:
                out.append(issue("MOSFET_" + label + "_RATING", "FAIL" if rated < required else "PASS", "error" if rated < required else "info",
                                 f"{label}必要値 {required:g}、指定定格 {rated:g}。温度/過渡/安全動作領域は未評価です。",
                                 "定格と安全動作領域、スイッチング損失、熱抵抗をデータシートで確認してください。", "数値定格の単純比較", [component["ref"]]))
