import json
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from circuitstudio.analysis import analyze, build_net_graph, parse_quantity
from circuitstudio.dsl import DslParseError, DslSchemaError, circuit_json, migrate_v1_to_v2, parse_circuit
from circuitstudio.kicad import compile_project, generate_schematic

ROOT = Path(__file__).resolve().parents[1]


def balanced_sexpr(text):
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not quoted


class CircuitDslTests(unittest.TestCase):
    def setUp(self):
        self.led_text = (ROOT / "samples" / "led.circuit.yaml").read_text(encoding="utf-8")
        self.led = parse_circuit(self.led_text)

    def test_json_yaml_sample_parses_and_roundtrips(self):
        self.assertEqual(parse_circuit(circuit_json(self.led)), self.led)

    def test_v1_to_v2_migration_is_lossless_and_v1_stays_supported(self):
        migrated = migrate_v1_to_v2(self.led)
        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual({key: value for key, value in migrated.items() if key != "schema_version"},
                         {key: value for key, value in self.led.items() if key != "schema_version"})
        self.assertEqual(parse_circuit(circuit_json(migrated)), migrated)
        self.assertEqual(parse_circuit(self.led_text), self.led)

    def test_v2_checks_power_rail_references_and_pcb_route_nets(self):
        data = parse_circuit((ROOT / "samples" / "led_v2.circuit.yaml").read_text(encoding="utf-8"))
        data["power_rails"][0]["net"] = "MISSING"
        data["pcb"]["routes"][0]["net"] = "MISSING"
        diagnostics, _ = analyze(data)
        ids = {item.id for item in diagnostics}
        self.assertIn("POWER_RAIL_NET_UNKNOWN", ids)
        self.assertIn("PCB_ROUTE_NET_UNKNOWN", ids)

    def test_rc_and_unselected_mosfet_samples_preserve_uncertainty(self):
        rc = parse_circuit((ROOT / "samples" / "rc_filter.circuit.yaml").read_text(encoding="utf-8"))
        rc_diagnostics, _ = analyze(rc)
        self.assertEqual(next(item for item in rc_diagnostics if item.id == "RESISTOR_POWER_RATING").status, "PASS")
        self.assertEqual(next(item for item in rc_diagnostics if item.id == "CAPACITOR_VOLTAGE_RATING").status, "PASS")
        switch = parse_circuit((ROOT / "samples" / "mosfet_switch_unverified.circuit.yaml").read_text(encoding="utf-8"))
        switch_diagnostics, _ = analyze(switch)
        self.assertIn("MOSFET_RATING_UNKNOWN", {item.id for item in switch_diagnostics})
        self.assertFalse(any(item.status == "FAIL" for item in switch_diagnostics))

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "optional jsonschema test dependency is absent")
    def test_versioned_json_schemas_accept_their_samples(self):
        import jsonschema
        for schema_name, sample_name in (("circuit.schema.json", "led.circuit.yaml"),
                                         ("circuit-v2.schema.json", "led_v2.circuit.yaml")):
            schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
            data = json.loads((ROOT / "samples" / sample_name).read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.validate(data, schema)

    def test_syntax_and_schema_errors_are_distinct(self):
        with self.assertRaises(DslParseError):
            parse_circuit('{"schema_version":')
        with self.assertRaises(DslSchemaError):
            parse_circuit('{"schema_version": 9}')
        with self.assertRaises(DslSchemaError):
            parse_circuit('{"schema_version":1,"schema_version":1}')
        with self.assertRaises(DslParseError):
            parse_circuit('{"schema_version":NaN}')

    def test_unknown_symbol_and_pin_are_not_guessed(self):
        bad = json.loads(self.led_text)
        bad["components"][0]["symbol"] = "Vendor:Unknown"
        diagnostics, _ = analyze(bad)
        self.assertIn("SYMBOL_UNKNOWN", {d.id for d in diagnostics})
        bad = json.loads(self.led_text)
        bad["components"][0]["pins"]["99"] = "VCC"
        diagnostics, _ = analyze(bad)
        self.assertIn("PIN_UNKNOWN", {d.id for d in diagnostics})

    def test_duplicate_reference_and_missing_net_fail(self):
        bad = json.loads(self.led_text)
        bad["components"][1]["ref"] = "R1"
        bad["components"][0]["pins"]["2"] = "DOES_NOT_EXIST"
        diagnostics, _ = analyze(bad)
        ids = {d.id for d in diagnostics}
        self.assertIn("DSL_DUPLICATE_REFERENCE", ids)
        self.assertIn("NET_UNKNOWN", ids)

    def test_si_prefix_conversion_and_resistor_power(self):
        self.assertAlmostEqual(parse_quantity("5mA"), 0.005)
        self.assertAlmostEqual(parse_quantity("1kΩ"), 1000)
        self.assertAlmostEqual(parse_quantity("0.125W"), 0.125)
        self.assertIsNone(parse_quantity("4parsecs"))
        diagnostics, _ = analyze(self.led)
        resistor = next(d for d in diagnostics if d.id == "RESISTOR_POWER_RATING")
        self.assertEqual(resistor.status, "PASS")
        self.assertIn("0.025", resistor.evidence)

    def test_net_graph_and_passive_open_pin_handling(self):
        diagnostics, graph = analyze(self.led)
        self.assertEqual(len(graph["LED_A"]), 2)
        led = next(c for c in self.led["components"] if c["ref"] == "D1")
        self.assertEqual(led["pins"], {"1": "GND", "2": "LED_A"})
        self.assertNotIn("PIN_UNSPECIFIED", {d.id for d in diagnostics})

    def test_hbridge_unknowns_block_native_output(self):
        data = parse_circuit((ROOT / "samples" / "hbridge_incomplete.circuit.yaml").read_text(encoding="utf-8"))
        diagnostics, _ = analyze(data)
        ids = {d.id for d in diagnostics}
        self.assertIn("HBRIDGE_OPERATING_DATA", ids)
        self.assertIn("HBRIDGE_DEAD_TIME", ids)
        with tempfile.TemporaryDirectory() as temp:
            result = compile_project(data, temp)
            project = Path(temp) / "RP2040_12V_HBridge"
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(list(project.glob("*.kicad_sch")))
            self.assertTrue((project / "report_ja.md").is_file())

    def test_generator_is_balanced_and_does_not_mutate_dsl(self):
        before = circuit_json(self.led)
        schematic = generate_schematic(self.led)
        self.assertTrue(balanced_sexpr(schematic))
        self.assertTrue(schematic.startswith("(kicad_sch (version 20250114)"))
        self.assertIn('"Device:R"', schematic)
        self.assertIn('(label "LED_A"', schematic)
        self.assertEqual(circuit_json(self.led), before)

    def test_only_explicit_no_connect_gets_a_marker(self):
        data = {"project": {"name": "pins"}, "design": {"intent": "pin marker"},
                "nets": [{"name": "VCC"}, {"name": "GND", "kind": "ground"}],
                "components": [{"ref": "J1", "symbol": "CircuitStudio:Generic_4Pin", "value": "HDR",
                                "pins": {"1": "VCC", "2": "GND"}, "no_connect": ["3"]}]}
        schematic = generate_schematic(data)
        self.assertEqual(schematic.count("(no_connect"), 1)
        self.assertIn('(no_connect (at 74.930 57.150)', schematic)
        self.assertNotIn('(no_connect (at 74.930 52.070)', schematic)

    def test_fixed_page_layout_limit_blocks_schematic(self):
        data = json.loads(self.led_text)
        data["project"]["name"] = "layout_limit"
        data["nets"] = [{"name": f"N{i}"} for i in range(1, 17)] + [{"name": "GND", "kind": "ground"}]
        data["components"] = [{"ref": f"R{i}", "symbol": "Device:R", "value": "1k", "pins": {"1": f"N{i}", "2": "GND"}}
                              for i in range(1, 17)]
        diagnostics, _ = analyze(data)
        self.assertIn("SCHEMATIC_LAYOUT_LIMIT", {d.id for d in diagnostics})
        with tempfile.TemporaryDirectory() as temp:
            result = compile_project(data, temp)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(list((Path(temp) / "layout_limit").glob("*.kicad_sch")))

    def test_compile_writes_project_reports_and_safe_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("circuitstudio.kicad.run_native_check", return_value={"status": "NOT_EXECUTED", "reason": "mocked"}):
                result = compile_project(self.led, temp)
            project = Path(temp) / "LED_Indicator"
            self.assertEqual(result["status"], "STRUCTURE_READY_ELECTRICAL_REVIEW_REQUIRED")
            self.assertEqual(result["native_erc"]["status"], "NOT_EXECUTED")
            for name in ("LED_Indicator.kicad_sch", "LED_Indicator.kicad_pro", "preview.svg", "BOM.csv", "diagnostics.json", "report_ja.md"):
                self.assertTrue((project / name).is_file(), name)
            saved = parse_circuit((project / "LED_Indicator.circuit.yaml").read_text(encoding="utf-8"))
            self.assertEqual(saved, self.led)
            self.assertNotIn("_generated_position", (project / "LED_Indicator.circuit.yaml").read_text(encoding="utf-8"))

    def test_nonempty_output_folder_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "LED_Indicator"
            project.mkdir()
            marker = project / "user.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                compile_project(self.led, temp)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
