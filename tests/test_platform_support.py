import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from circuitstudio.kicad import _symbol_library_path, find_kicad_cli, kicad_gui_command
from circuitstudio.pcbgen import find_kicad_python
from circuitstudio.spice import find_ngspice


class PlatformSupportTests(unittest.TestCase):
    def test_macos_bundle_cli_and_symbol_library_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp) / "KiCad.app"
            cli = app / "Contents" / "MacOS" / "kicad-cli"
            symbols = app / "Contents" / "SharedSupport" / "symbols"
            cli.parent.mkdir(parents=True)
            symbols.mkdir(parents=True)
            cli.touch()
            symbol_file = symbols / "Device.kicad_sym"
            symbol_file.touch()
            with patch.dict(os.environ, {"KICAD_CLI": str(cli)}), patch(
                "circuitstudio.kicad.platform.system", return_value="Darwin"
            ):
                self.assertEqual(find_kicad_cli(), str(cli))
                self.assertEqual(_symbol_library_path("Device"), symbol_file)

    def test_macos_gui_launch_uses_open_and_preserves_unicode_path(self):
        with tempfile.TemporaryDirectory() as temp:
            cli = Path(temp) / "KiCad.app" / "Contents" / "MacOS" / "kicad-cli"
            cli.parent.mkdir(parents=True)
            cli.touch()
            schematic = Path(temp) / "回路図.kicad_sch"
            with patch("circuitstudio.kicad.platform.system", return_value="Darwin"), patch(
                "circuitstudio.kicad.shutil.which", return_value="/usr/bin/open"
            ):
                command = kicad_gui_command(schematic, str(cli))
            self.assertEqual(command, ["/usr/bin/open", "-a", str(cli.parents[2]), str(schematic)])

    def test_windows_gui_launch_keeps_native_executable_behavior(self):
        with tempfile.TemporaryDirectory() as temp:
            cli = Path(temp) / "bin" / "kicad-cli.exe"
            gui = cli.with_name("kicad.exe")
            cli.parent.mkdir()
            cli.touch()
            gui.touch()
            schematic = Path(temp) / "回路図.kicad_sch"
            with patch("circuitstudio.kicad.platform.system", return_value="Windows"):
                self.assertEqual(kicad_gui_command(schematic, str(cli)), [str(gui), str(schematic)])

    def test_posix_ngspice_uses_native_executable_only(self):
        with tempfile.TemporaryDirectory() as temp:
            native = Path(temp) / "ngspice"
            windows_binary = Path(temp) / "ngspice.exe"
            native.touch()
            native.chmod(0o755)
            windows_binary.touch()
            with patch.dict(os.environ, {"NGSPICE": str(native)}), patch(
                "circuitstudio.spice.platform.system", return_value="Darwin"
            ), patch("circuitstudio.spice.os.access", return_value=True):
                self.assertEqual(find_ngspice(), str(native))
            with patch.dict(os.environ, {"NGSPICE": str(windows_binary)}), patch(
                "circuitstudio.spice.platform.system", return_value="Darwin"
            ), patch("circuitstudio.spice.os.access", return_value=True), patch(
                "circuitstudio.spice.shutil.which", return_value=None
            ):
                self.assertIsNone(find_ngspice())

    def test_macos_pcbnew_runtime_requires_matching_kicad_version(self):
        with tempfile.TemporaryDirectory() as temp:
            cli = Path(temp) / "kicad-cli"
            python = Path(temp) / "python3"
            cli.touch()
            python.touch()
            completed = type("Completed", (), {"returncode": 0, "stdout": "10.0.7\n"})()
            with patch.dict(os.environ, {"KICAD_CLI": str(cli), "KICAD_PYTHON": str(python)}), patch(
                "circuitstudio.pcbgen.platform.system", return_value="Darwin"
            ), patch("circuitstudio.pcbgen.subprocess.run", return_value=completed) as run:
                self.assertEqual(find_kicad_python(), python)
                self.assertEqual(run.call_count, 2)

            mismatch = type("Completed", (), {"returncode": 0, "stdout": "9.0.6\n"})()
            with patch.dict(os.environ, {"KICAD_CLI": str(cli), "KICAD_PYTHON": str(python)}), patch(
                "circuitstudio.pcbgen.platform.system", return_value="Darwin"
            ), patch("circuitstudio.pcbgen.subprocess.run", side_effect=[mismatch, completed]):
                self.assertIsNone(find_kicad_python())

            with patch.dict(os.environ, {"KICAD_CLI": str(cli), "KICAD_PYTHON": ""}), patch(
                "circuitstudio.pcbgen.platform.system", return_value="Darwin"
            ):
                self.assertIsNone(find_kicad_python())


if __name__ == "__main__":
    unittest.main()
