"""CircuitDSL parsing and structural validation; YAML is loaded with safe_load when available."""

import json
import math
import re
from copy import deepcopy
from urllib.parse import urlparse

MAX_DSL_BYTES = 1_000_000
ROOT_KEYS_V1 = {"schema_version", "project", "design", "nets", "components"}
ROOT_KEYS_V2 = ROOT_KEYS_V1 | {"metadata", "power_rails", "safety_notes", "pcb", "diagnostics", "suggestions", "simulation"}


class DslError(ValueError):
    pass


class DslParseError(DslError):
    pass


class DslSchemaError(DslError):
    pass


def parse_circuit(text: str) -> dict:
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_DSL_BYTES:
        raise DslParseError("DSLが上限 1 MB を超えています。")
    try:
        data = json.loads(text, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    except DslSchemaError:
        raise
    except json.JSONDecodeError as json_error:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError:
            raise DslParseError(
                f"JSON/YAML構文エラー: {json_error.msg} (line {json_error.lineno}, column {json_error.colno})。"
                "完全なYAMLには PyYAML が必要です。JSON形式は追加依存なしで使えます。"
            ) from json_error
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = f" line {mark.line + 1}, column {mark.column + 1}" if mark else ""
            raise DslParseError(f"YAML構文エラー:{where} {exc}") from exc
    except ValueError as exc:
        raise DslParseError(f"DSL構文エラー: {exc}") from exc
    if not isinstance(data, dict):
        raise DslSchemaError("DSLのルートはオブジェクトである必要があります。")
    validate_schema(data)
    return data


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DslSchemaError(f"重複キー '{key}' は使用できません。")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"JSON標準外の数値 {value} は使用できません。")


def validate_schema(data: dict) -> None:
    errors = []
    version = data.get("schema_version")
    root_keys = ROOT_KEYS_V1 if version == 1 else ROOT_KEYS_V2 if version == 2 else ROOT_KEYS_V1
    unknown_root = set(data) - root_keys
    if unknown_root:
        errors.append(f"未知のトップレベル項目: {', '.join(sorted(unknown_root))}")
    if type(version) is not int or version not in {1, 2}:
        errors.append("schema_version は 1 または 2 を指定してください。")
    project = data.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("name"), str) or not project["name"].strip():
        errors.append("project.name は空でない文字列である必要があります。")
    elif len(project["name"]) > 100 or any(ch in project["name"] for ch in "/\\:\x00") or ".." in project["name"]:
        errors.append("project.name にパス区切り文字、'..'、または100文字超は使えません。")
    if isinstance(project, dict):
        if set(project) - {"name", "description"}:
            errors.append("project に未知の項目があります。")
        if "description" in project and (not isinstance(project["description"], str) or len(project["description"]) > 2000):
            errors.append("project.description は2000文字以下の文字列です。")
    design = data.get("design")
    if not isinstance(design, dict) or not isinstance(design.get("intent"), str):
        errors.append("design.intent は文字列で指定してください。")
    elif len(design["intent"]) > 2000:
        errors.append("design.intent は2000文字以下にしてください。")
    if isinstance(design, dict):
        allowed_design = {"intent", "architecture", "parameters", "constraints", "pcb_constraints", "unknowns", "datasheets", "rules"}
        if set(design) - allowed_design:
            errors.append("design に未知の項目があります。")
        if "architecture" in design and not isinstance(design["architecture"], str):
            errors.append("design.architecture は文字列である必要があります。")
    for field in ("parameters", "constraints", "pcb_constraints"):
        if field in (design or {}) and not isinstance(design[field], dict):
            errors.append(f"design.{field} はオブジェクトである必要があります。")
    if isinstance(design, dict) and isinstance(design.get("parameters", {}), dict):
        if any(not isinstance(v, (str, int, float, bool, type(None))) or isinstance(v, float) and not math.isfinite(v)
               for v in design.get("parameters", {}).values()):
            errors.append("design.parameters の値は有限数値、文字列、boolean、nullにしてください。")
    for field in ("unknowns", "datasheets", "rules"):
        if field in (design or {}) and not isinstance(design[field], list):
            errors.append(f"design.{field} は配列である必要があります。")
        elif isinstance(design, dict) and field in design and any(not isinstance(v, str) for v in design[field]):
            errors.append(f"design.{field} の全要素は文字列である必要があります。")
    if isinstance(design, dict) and isinstance(design.get("datasheets", []), list):
        for value in design.get("datasheets", []):
            if isinstance(value, str) and (urlparse(value).scheme not in {"http", "https"} or not urlparse(value).netloc):
                errors.append(f"datasheetsの参照はhttp/https URIにしてください: {value}")
    nets = data.get("nets")
    if not isinstance(nets, list):
        errors.append("nets は配列である必要があります。")
    else:
        for i, net in enumerate(nets):
            if not isinstance(net, dict) or not isinstance(net.get("name"), str) or not net["name"].strip():
                errors.append(f"nets[{i}].name は空でない文字列である必要があります。")
            elif len(net["name"]) > 80 or any(c.isspace() or c in '()\"' for c in net["name"]):
                errors.append(f"nets[{i}].name に空白または S式の区切り文字は使えません。")
            if isinstance(net, dict) and net.get("kind", "signal") not in {"signal", "power", "ground"}:
                errors.append(f"nets[{i}].kind は signal/power/ground のいずれかです。")
            if isinstance(net, dict):
                if set(net) - {"name", "kind", "voltage_V", "description"}:
                    errors.append(f"nets[{i}] に未知の項目があります。")
                if "description" in net and not isinstance(net["description"], str):
                    errors.append(f"nets[{i}].description は文字列です。")
                if "voltage_V" in net and not isinstance(net["voltage_V"], (str, int, float, type(None))):
                    errors.append(f"nets[{i}].voltage_V は数値、単位文字列、nullのいずれかです。")
                if isinstance(net.get("voltage_V"), float) and not math.isfinite(net["voltage_V"]):
                    errors.append(f"nets[{i}].voltage_V は有限数値にしてください。")
    components = data.get("components")
    if not isinstance(components, list) or len(components) > 200:
        errors.append("components は200個以下の配列である必要があります。")
    else:
        for i, component in enumerate(components):
            if not isinstance(component, dict):
                errors.append(f"components[{i}] はオブジェクトである必要があります。")
                continue
            for field in ("ref", "symbol", "value"):
                if not isinstance(component.get(field), str) or not component[field].strip():
                    errors.append(f"components[{i}].{field} は空でない文字列である必要があります。")
            if isinstance(component.get("ref"), str) and not re.fullmatch(r"[A-Za-z]{1,4}[0-9]+[A-Za-z]?", component["ref"]):
                errors.append(f"components[{i}].ref は R1/U2 の形式で指定してください。")
            if isinstance(component.get("value"), str) and len(component["value"]) > 200:
                errors.append(f"components[{i}].value は200文字以下です。")
            for field in ("part_number", "footprint", "datasheet"):
                if field in component and not isinstance(component[field], str):
                    errors.append(f"components[{i}].{field} は文字列である必要があります。")
            if not isinstance(component.get("pins"), dict):
                errors.append(f"components[{i}].pins は pin番号からnet名へのオブジェクトである必要があります。")
            elif any(not isinstance(k, str) or not isinstance(v, str) for k, v in component["pins"].items()):
                errors.append(f"components[{i}].pins のキーと値は文字列である必要があります。")
            if "no_connect" in component and (not isinstance(component["no_connect"], list) or any(not isinstance(v, str) for v in component["no_connect"])):
                errors.append(f"components[{i}].no_connect は pin番号の配列である必要があります。")
            elif isinstance(component.get("no_connect"), list) and len(set(component["no_connect"])) != len(component["no_connect"]):
                errors.append(f"components[{i}].no_connect に重複pinがあります。")
            if "ratings" in component and not isinstance(component["ratings"], dict):
                errors.append(f"components[{i}].ratings はオブジェクトである必要があります。")
            if isinstance(component.get("ratings"), dict) and any(not isinstance(v, (str, int, float, type(None))) for v in component["ratings"].values()):
                errors.append(f"components[{i}].ratings は数値、文字列、nullの値を指定してください。")
            if isinstance(component.get("ratings"), dict) and any(isinstance(v, float) and not math.isfinite(v) for v in component["ratings"].values()):
                errors.append(f"components[{i}].ratings は有限数値を指定してください。")
            component_keys = {"ref", "symbol", "value", "part_number", "footprint", "datasheet", "pins", "no_connect", "ratings"}
            if version == 2:
                component_keys |= {"placement", "properties"}
            if set(component) - component_keys:
                errors.append(f"components[{i}] に未知の項目があります。")
    if version == 2:
        _validate_v2(data, errors)
    if errors:
        raise DslSchemaError("スキーマエラー:\n- " + "\n- ".join(errors))


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_v2(data, errors):
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict) or set(metadata) - {"author", "revision", "description"}:
        errors.append("metadata は author/revision/description のみを持つオブジェクトです。")
    elif any(not isinstance(value, str) or len(value) > 2000 for value in metadata.values()):
        errors.append("metadata の値は2000文字以下の文字列です。")
    simulation = data.get("simulation")
    if simulation is not None:
        allowed = {"analysis", "step_s", "stop_s", "source", "observe_nets"}
        if not isinstance(simulation, dict) or set(simulation) - allowed or simulation.get("analysis") != "transient":
            errors.append("simulation は analysis='transient' と step_s/stop_s/source/observe_nets を持つオブジェクトです。")
        else:
            for key in ("step_s", "stop_s"):
                if not _finite_number(simulation.get(key)) or simulation[key] <= 0:
                    errors.append(f"simulation.{key} は正の有限秒数です。")
            if all(_finite_number(simulation.get(key)) for key in ("step_s", "stop_s")) and simulation["step_s"] >= simulation["stop_s"]:
                errors.append("simulation.step_s は stop_s より小さくしてください。")
            source = simulation.get("source")
            source_keys = {"positive_net", "negative_net", "initial_voltage_V", "pulsed_voltage_V", "delay_s", "rise_s", "fall_s", "pulse_width_s", "period_s"}
            if not isinstance(source, dict) or set(source) != source_keys or any(not isinstance(source.get(key), str) for key in ("positive_net", "negative_net")):
                errors.append("simulation.source はネット名2個とPULSE電圧/時間条件をすべて指定してください。")
            elif any(not _finite_number(source[key]) for key in source_keys - {"positive_net", "negative_net"}):
                errors.append("simulation.source の電圧/時間値は有限数値で指定してください。")
            elif any(source[key] < 0 for key in ("delay_s", "rise_s", "fall_s", "pulse_width_s")) or source["period_s"] <= 0 or source["pulse_width_s"] > source["period_s"]:
                errors.append("simulation.source のPULSE時間条件が不正です。")
            observe = simulation.get("observe_nets")
            if not isinstance(observe, list) or not observe or any(not isinstance(net, str) for net in observe) or len(set(observe)) != len(observe):
                errors.append("simulation.observe_nets は重複のない非空ネット名配列です。")
    for field in ("safety_notes",):
        value = data.get(field, [])
        if not isinstance(value, list) or any(not isinstance(item, str) or len(item) > 2000 for item in value):
            errors.append(f"{field} は2000文字以下の文字列配列です。")
    rails = data.get("power_rails", [])
    if not isinstance(rails, list):
        errors.append("power_rails は配列です。")
    else:
        allowed = {"net", "nominal_voltage_V", "min_voltage_V", "max_voltage_V", "current_limit_A"}
        for index, rail in enumerate(rails):
            if not isinstance(rail, dict) or set(rail) - allowed or not isinstance(rail.get("net"), str):
                errors.append(f"power_rails[{index}] はnetと電圧/電流制約を持つオブジェクトです。")
            elif any(value is not None and not isinstance(value, (str, int, float)) for key, value in rail.items() if key != "net"):
                errors.append(f"power_rails[{index}] の制約値は数値、単位文字列、nullです。")
            elif any(isinstance(value, float) and not math.isfinite(value) for key, value in rail.items() if key != "net"):
                errors.append(f"power_rails[{index}] の制約値は有限数値です。")
    pcb = data.get("pcb", {})
    if not isinstance(pcb, dict) or set(pcb) - {"layers", "board_thickness_mm", "outline", "constraints", "placements", "mounting_holes", "routes"}:
        errors.append("pcb は layers/board_thickness_mm/outline/constraints/placements/mounting_holes/routes のみを持つオブジェクトです。")
    elif pcb:
        if "layers" in pcb and (type(pcb["layers"]) is not int or pcb["layers"] not in {2, 4}):
            errors.append("pcb.layers は2または4です。")
        if "board_thickness_mm" in pcb and (not _finite_number(pcb["board_thickness_mm"]) or pcb["board_thickness_mm"] <= 0):
            errors.append("pcb.board_thickness_mm は正の有限値です。")
        outline = pcb.get("outline", {})
        if outline and (not isinstance(outline, dict) or set(outline) - {"width_mm", "height_mm", "origin_x_mm", "origin_y_mm"}
                        or not all(_finite_number(outline.get(field)) and outline[field] > 0 for field in ("width_mm", "height_mm"))):
            errors.append("pcb.outline は正のwidth_mm/height_mmと任意の数値原点を指定します。")
        constraints = pcb.get("constraints", {})
        if not isinstance(constraints, dict) or set(constraints) - {"clearance_mm", "trace_width_mm", "copper_oz", "temperature_rise_C"}:
            errors.append("pcb.constraints に未知の項目があります。")
        elif any(not _finite_number(value) or value <= 0 for value in constraints.values() if value is not None):
            errors.append("pcb.constraints の数値は正の有限値です。")
        placements = pcb.get("placements", [])
        if not isinstance(placements, list):
            errors.append("pcb.placements は配列です。")
        else:
            for index, item in enumerate(placements):
                if (not isinstance(item, dict) or set(item) - {"ref", "x_mm", "y_mm", "rotation_deg", "side"}
                        or not isinstance(item.get("ref"), str)
                        or not all(_finite_number(item.get(key)) for key in ("x_mm", "y_mm"))
                        or not isinstance(item.get("side", "top"), str)
                        or item.get("side", "top") not in {"top", "bottom"}
                        or not _finite_number(item.get("rotation_deg", 0))):
                    errors.append(f"pcb.placements[{index}] はref/x_mm/y_mm/rotation_deg/sideが必要です。")
        holes = pcb.get("mounting_holes", [])
        if not isinstance(holes, list) or any(not isinstance(item, dict) or set(item) != {"x_mm", "y_mm", "diameter_mm"}
                                              or not all(_finite_number(item.get(key)) and item[key] > 0 for key in ("x_mm", "y_mm", "diameter_mm"))
                                              for item in holes):
            errors.append("pcb.mounting_holes は正の数値x_mm/y_mm/diameter_mmの配列です。")
        routes = pcb.get("routes", [])
        if not isinstance(routes, list):
            errors.append("pcb.routes は配列です。")
        else:
            for index, route in enumerate(routes):
                points = route.get("points") if isinstance(route, dict) else None
                if (not isinstance(route, dict) or set(route) - {"net", "layer", "width_mm", "points"}
                        or not isinstance(route.get("net"), str) or not isinstance(route.get("layer"), str)
                        or route.get("layer") not in {"F.Cu", "B.Cu"}
                        or ("width_mm" in route and (not _finite_number(route["width_mm"]) or route["width_mm"] <= 0))
                        or not isinstance(points, list) or len(points) < 2
                        or any(not isinstance(point, dict) or set(point) != {"x_mm", "y_mm"}
                               or not all(_finite_number(point.get(key)) for key in ("x_mm", "y_mm")) for point in points)):
                    errors.append(f"pcb.routes[{index}] はnet/layer/width_mm/2点以上のpointsが必要です。")
    for component in data.get("components", []):
        if not isinstance(component, dict):
            continue
        placement = component.get("placement")
        if placement is not None and (not isinstance(placement, dict) or set(placement) - {"x_mm", "y_mm", "rotation_deg", "side"}
                                      or not all(_finite_number(placement.get(key)) for key in ("x_mm", "y_mm"))
                                      or not isinstance(placement.get("side", "top"), str)
                                      or placement.get("side", "top") not in {"top", "bottom"}
                                      or not _finite_number(placement.get("rotation_deg", 0))):
            errors.append(f"{component.get('ref', '?')}.placement の座標/回転/面が不正です。")
        properties = component.get("properties", {})
        if not isinstance(properties, dict) or any(not isinstance(key, str) or not isinstance(value, (str, int, float, bool, type(None)))
                                                   for key, value in properties.items()):
            errors.append(f"{component.get('ref', '?')}.properties はスカラー値のオブジェクトです。")
        elif any(isinstance(value, float) and not math.isfinite(value) for value in properties.values()):
            errors.append(f"{component.get('ref', '?')}.properties の数値は有限値です。")
    for field in ("diagnostics", "suggestions"):
        values = data.get(field, [])
        if not isinstance(values, list):
            errors.append(f"{field} は配列です。")
            continue
        for index, item in enumerate(values):
            if not isinstance(item, dict):
                errors.append(f"{field}[{index}] はオブジェクトです。")
            elif field == "diagnostics" and (set(item) - {"id", "status", "severity", "target", "evidence", "recommendation", "method"}
                                               or not all(isinstance(item.get(key), str) for key in ("id", "status", "severity", "evidence", "recommendation", "method"))
                                               or item.get("status") not in {"PASS", "FAIL", "WARNING", "UNKNOWN", "BLOCKED", "NOT_VERIFIED", "NOT_EXECUTED"}):
                errors.append(f"diagnostics[{index}] の形式/状態が不正です。")
            elif field == "suggestions" and (set(item) - {"id", "summary", "patch"}
                                                or not all(isinstance(item.get(key), str) for key in ("id", "summary", "patch"))):
                errors.append(f"suggestions[{index}] はid/summary/patchを持つ文字列オブジェクトです。")


def migrate_v1_to_v2(data: dict) -> dict:
    """Explicit, lossless migration; v1 inputs continue to parse without migration."""
    validate_schema(data)
    migrated = deepcopy(data)
    migrated["schema_version"] = 2
    validate_schema(migrated)
    return migrated


def circuit_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def safe_project_stem(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("._-")
    return (stem[:64] or "CircuitProject")
