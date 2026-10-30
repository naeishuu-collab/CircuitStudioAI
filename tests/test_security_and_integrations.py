import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from circuitstudio.dsl import DslParseError, DslSchemaError, MAX_DSL_BYTES, parse_circuit
from circuitstudio.kicad import find_kicad_cli
from circuitstudio.pcb import inspect_board
from circuitstudio.pcbgen import find_kicad_python, generate_pcb
from circuitstudio.providers import OpenAICompatibleProvider, ProviderError
from circuitstudio.spice import simulate


class SecurityAndIntegrationTests(unittest.TestCase):
    def test_oversized_dsl_is_rejected_before_parse(self):
        with self.assertRaises(DslParseError):
            parse_circuit(" " * (MAX_DSL_BYTES + 1))

    def test_path_traversal_project_names_are_rejected(self):
        base = {"schema_version": 1, "project": {"name": "../outside"}, "design": {"intent": "x"}, "nets": [], "components": []}
        with self.assertRaises(DslSchemaError):
            parse_circuit(json.dumps(base))
        base["project"]["name"] = "safe"
        base["components"] = [{"ref": "X1", "symbol": "CircuitStudio:Generic_4Pin", "value": '"); (kicad_sch', "pins": {}}]
        self.assertEqual(parse_circuit(json.dumps(base))["components"][0]["value"], '"); (kicad_sch')

    def test_hostile_value_is_serialized_as_data_not_executable_s_expression(self):
        from circuitstudio.kicad import generate_schematic
        source = json.loads((Path(__file__).resolve().parents[1] / "samples" / "led.circuit.yaml").read_text(encoding="utf-8"))
        source["components"][0]["value"] = '"; (at 0 0 0) (uuid "injected'
        schematic = generate_schematic(source)
        self.assertIn('\\"; (at 0 0 0) (uuid \\"injected', schematic)
        self.assertEqual(schematic.count("(kicad_sch"), 1)

    @unittest.skipUnless(find_kicad_python(), "KiCad bundled pcbnew Python is absent")
    def test_footprint_path_traversal_is_rejected_before_board_write(self):
        root = Path(__file__).resolve().parents[1]
        data = parse_circuit((root / "samples" / "led_v2.circuit.yaml").read_text(encoding="utf-8"))
        data["components"][0]["footprint"] = "../../outside:evil"
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "evil.kicad_pcb"
            result = generate_pcb(data, target)
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(target.exists())

    @unittest.skipUnless(find_kicad_python(), "KiCad bundled pcbnew Python is absent")
    def test_pcb_generation_blocks_without_declared_board_thickness(self):
        root = Path(__file__).resolve().parents[1]
        data = parse_circuit((root / "samples" / "led_v2.circuit.yaml").read_text(encoding="utf-8"))
        del data["pcb"]["board_thickness_mm"]
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "unknown_thickness.kicad_pcb"
            result = generate_pcb(data, target)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(target.exists())

    def test_remote_plain_http_api_key_is_refused(self):
        with self.assertRaises(ProviderError):
            OpenAICompatibleProvider(base_url="http://example.com/v1", api_key="test-secret")

    def test_no_openai_key_reports_manual_mode_without_network(self):
        provider = OpenAICompatibleProvider(base_url="https://api.openai.com/v1", api_key="")
        with self.assertRaises(ProviderError) as caught:
            provider.generate("generate a circuit", {})
        self.assertNotIn("test-secret", str(caught.exception))

    def test_pcb_inspection_is_read_only_and_marks_drc_unexecuted_without_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            board = Path(temp) / "sample.kicad_pcb"
            content = '(kicad_pcb (version 20250114) (net 1 "GND") (segment (width 0.25) (layer "F.Cu")) (gr_text "literal (segment )" (layer "F.SilkS")))'
            board.write_text(content, encoding="utf-8")
            before = {path.name for path in Path(temp).iterdir()}
            result = inspect_board(board)
            self.assertEqual(result["counts"]["segments"], 1)
            if not find_kicad_cli():
                self.assertEqual(result["status"], "NOT_EXECUTED")
            self.assertEqual(board.read_text(encoding="utf-8"), content)
            self.assertEqual({path.name for path in Path(temp).iterdir()}, before)

    def test_deeply_nested_pcb_input_is_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            board = Path(temp) / "nested.kicad_pcb"
            board.write_text("(kicad_pcb " + "(" * 300 + ")" * 300 + ")", encoding="ascii")
            with self.assertRaises(ValueError):
                inspect_board(board)

    def test_missing_ngspice_is_not_simulation_success(self):
        with tempfile.TemporaryDirectory() as temp:
            netlist = Path(temp) / "empty.cir"
            netlist.write_text("* no circuit model\n.end\n", encoding="ascii")
            with patch("circuitstudio.spice.find_ngspice", return_value=None):
                result = simulate(netlist)
            self.assertEqual(result["status"], "NOT_EXECUTED")
            self.assertIn("波形は生成していません", result["reason"])


if __name__ == "__main__":
    unittest.main()
