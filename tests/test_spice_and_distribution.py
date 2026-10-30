import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from circuitstudio.dsl import migrate_v1_to_v2, parse_circuit
from circuitstudio.spice import find_ngspice, generate_spice_deck, simulate


ROOT = Path(__file__).resolve().parents[1]


class SpiceTests(unittest.TestCase):
    def setUp(self):
        self.data = parse_circuit((ROOT / "samples" / "rc_filter_spice_v2.circuit.yaml").read_text(encoding="utf-8"))

    def test_v1_migration_keeps_original_and_generates_explicit_rc_deck(self):
        source_v1 = parse_circuit((ROOT / "samples" / "rc_filter.circuit.yaml").read_text(encoding="utf-8"))
        before = dict(source_v1)
        migrated = migrate_v1_to_v2(source_v1)
        migrated["simulation"] = self.data["simulation"]
        deck = generate_spice_deck(migrated)
        self.assertEqual(source_v1, before)
        self.assertIn("R1 N003 N002 10000", deck)
        self.assertIn("C1 N002 0 1e-07", deck)
        self.assertIn("PULSE(0 5", deck)
        self.assertIn("wrdata transient.csv v(N002)", deck)

    def test_unknown_component_model_is_not_guessed(self):
        data = dict(self.data)
        data["components"] = self.data["components"] + [{"ref": "Q1", "symbol": "CircuitStudio:NMOS_3Pin", "value": "unknown",
            "pins": {"1": "RC_OUT", "2": "GND", "3": "VCC"}}]
        with self.assertRaisesRegex(ValueError, "モデルがありません"):
            generate_spice_deck(data)

    def test_wrong_component_units_are_rejected(self):
        data = dict(self.data)
        data["components"] = [dict(component) for component in self.data["components"]]
        data["components"][1]["value"] = "10kV"
        with self.assertRaisesRegex(ValueError, "単位"):
            generate_spice_deck(data)

    def test_external_shell_commands_are_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "unsafe.cir"
            deck.write_text("* unsafe\n.control\nshell echo unsafe\n.endc\n.end\n", encoding="utf-8")
            self.assertEqual(simulate(deck)["status"], "BLOCKED")

    def test_model_path_escape_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "project"
            folder.mkdir()
            deck = folder / "unsafe.cir"
            deck.write_text('.include "../outside.lib"\n.end\n', encoding="utf-8")
            result = simulate(deck)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("フォルダー内", result["reason"])

    def test_existing_waveform_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "sample.cir"
            deck.write_text(".control\nwrdata existing.csv v(1)\n.endc\n.end\n", encoding="utf-8")
            waveform = Path(temp) / "existing.csv"
            waveform.write_text("keep", encoding="utf-8")
            self.assertEqual(simulate(deck)["status"], "BLOCKED")
            self.assertEqual(waveform.read_text(encoding="utf-8"), "keep")

    @unittest.skipUnless(find_ngspice(), "ngspice executable is absent")
    def test_ngspice_runs_rc_transient_and_writes_real_csv(self):
        deck_text = generate_spice_deck(self.data)
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "rc.cir"
            deck.write_text(deck_text, encoding="utf-8")
            result = simulate(deck)
            self.assertEqual(result["status"], "PASS", result)
            self.assertEqual(len(result["csv_outputs"]), 1)
            csv_file = Path(result["csv_outputs"][0])
            self.assertGreater(csv_file.stat().st_size, 100)
            self.assertIn("time", csv_file.read_text(encoding="utf-8", errors="replace").lower())


if __name__ == "__main__":
    unittest.main()
