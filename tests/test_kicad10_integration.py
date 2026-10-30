"""Real KiCad 10 checks; skipped only when the corresponding native tool is absent."""

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from circuitstudio.dsl import parse_circuit
from circuitstudio.kicad import compile_project, find_kicad_cli, generate_schematic, run_native_check
from circuitstudio.pcbgen import find_kicad_python


ROOT = Path(__file__).resolve().parents[1]
V2_SAMPLE = ROOT / "samples" / "led_v2.circuit.yaml"


@unittest.skipUnless(find_kicad_cli(), "KiCad CLI is not installed")
class KiCad10CliTests(unittest.TestCase):
    def test_existing_led_sample_file_is_cli_valid_and_unmodified(self):
        project = ROOT / "samples" / "LED_Indicator"
        schematic = project / "LED_Indicator.kicad_sch"
        board = project / "LED_Indicator.kicad_pcb"
        before = {path.name for path in project.iterdir()}
        self.assertEqual(run_native_check("erc", schematic)["status"], "PASS")
        self.assertEqual(run_native_check("netlist", schematic)["status"], "PASS")
        self.assertEqual(run_native_check("svg", schematic)["status"], "PASS")
        self.assertEqual(run_native_check("drc", board)["status"], "PASS")
        self.assertEqual({path.name for path in project.iterdir()}, before)

    def test_compiled_v2_project_passes_erc_exports_and_board_drc(self):
        data = parse_circuit(V2_SAMPLE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            result = compile_project(data, temp)
            project = Path(temp) / "LED_Indicator_v2"
            self.assertEqual(result["native_erc"]["status"], "PASS")
            self.assertEqual(result["native_erc"]["violation_total"], 0)
            exports = result["native_exports"]
            self.assertEqual(exports["netlist"]["status"], "PASS")
            self.assertEqual(exports["svg"]["status"], "PASS")
            netlist = ET.parse(project / "LED_Indicator_v2-netlist.xml").getroot()
            nets = {net.attrib["name"].lstrip("/"): {(node.attrib["ref"], node.attrib["pin"]) for node in net.findall("node")}
                    for net in netlist.findall(".//nets/net")}
            self.assertEqual(nets["VCC"], {("J1", "1"), ("R1", "1")})
            self.assertEqual(nets["LED_A"], {("R1", "2"), ("D1", "2")})
            self.assertEqual(nets["GND"], {("J1", "2"), ("D1", "1")})
            self.assertTrue((project / "kicad-svg" / "LED_Indicator_v2.svg").is_file())
            pcb = exports["pcb"]
            if find_kicad_python():
                self.assertEqual(pcb["status"], "ROUTED")
                self.assertEqual(pcb["native_drc"]["status"], "PASS")
                self.assertEqual(pcb["native_drc"]["violation_total"], 0)
                self.assertEqual(pcb["manufacturing_status"], "NOT_PROVEN")
                self.assertEqual(pcb["trace_capacity"]["status"], "NOT_EXECUTED")
                self.assertTrue((project / "LED_Indicator_v2.kicad_pcb").is_file())
            else:
                self.assertEqual(pcb["status"], "NOT_EXECUTED")

    def test_cli_validation_does_not_create_sidecars_next_to_source(self):
        data = parse_circuit((ROOT / "samples" / "led.circuit.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            schematic = folder / "isolated.kicad_sch"
            schematic.write_text(generate_schematic(data), encoding="utf-8")
            before = {path.name for path in folder.iterdir()}
            result = run_native_check("erc", schematic)
            self.assertEqual(result["status"], "WARNING")
            self.assertEqual({path.name for path in folder.iterdir()}, before)

    def test_rc_and_unselected_mosfet_schematics_load_in_kicad_cli(self):
        for sample in ("rc_filter.circuit.yaml", "mosfet_switch_unverified.circuit.yaml"):
            with self.subTest(sample=sample), tempfile.TemporaryDirectory() as temp:
                data = parse_circuit((ROOT / "samples" / sample).read_text(encoding="utf-8"))
                result = compile_project(data, temp)
                self.assertTrue((Path(temp) / data["project"]["name"] / f"{data['project']['name']}.kicad_sch").is_file())
                self.assertIn(result["native_erc"]["status"], {"PASS", "WARNING"})


if __name__ == "__main__":
    unittest.main()
