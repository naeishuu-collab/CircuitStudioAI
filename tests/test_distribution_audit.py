from contextlib import redirect_stdout
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.audit_distribution import main, scan_distribution


class DistributionAuditTests(unittest.TestCase):
    def test_clean_files_and_zip_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text("safe sample\n", encoding="utf-8")
            with ZipFile(root / "app.zip", "w") as archive:
                archive.writestr("docs/manual.txt", "no local paths or credentials\n")
            self.assertEqual(scan_distribution(root), [])

    def test_detects_escaped_local_path_and_credential_without_returning_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            local_path = "C:" + "\\" + "Users" + "\\" + "example" + "\\" + "CircuitStudio"
            mac_path = "/" + "Users" + "/" + "example" + "/Library"
            (root / "diagnostics.json").write_text(
                json.dumps({"project": local_path, "mac_export": mac_path}), encoding="utf-8"
            )
            with ZipFile(root / "app.zip", "w") as archive:
                archive.writestr("config.txt", "sk-" + "a" * 30 + "\n")
            findings = scan_distribution(root)
            self.assertEqual(
                findings,
                [("app.zip", "credential"), ("diagnostics.json", "local-path")],
            )
            self.assertNotIn("example", repr(findings))
            self.assertNotIn("sk-", repr(findings))
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main([str(root)]), 1)
            self.assertIn("FAIL credential: count=1", output.getvalue())
            self.assertNotIn("example", output.getvalue())
            self.assertNotIn("sk-", output.getvalue())


if __name__ == "__main__":
    unittest.main()
