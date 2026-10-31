"""Fail a distribution build if packaged text contains local paths or credentials."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile


TEXT_SUFFIXES = {
    ".bat", ".cir", ".cfg", ".csv", ".ini", ".json", ".md", ".ps1",
    ".py", ".sh", ".spec", ".txt", ".xml", ".yaml", ".yml",
}
LOCAL_PATH = re.compile(rb'''(?i)(?:[A-Z]:\\Users\\[^\\/\s"'<>]+|/Users/[^/\s"'<>]+)''')
CREDENTIAL = re.compile(
    rb'''(?i)\b(?:sk-[a-z0-9_-]{20,}|gh[pousr]_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b'''
)


def _text_findings(data: bytes) -> list[str]:
    # JSON-escaped Windows paths are normalized so they match the same rule.
    normalized = data.replace(b"\\\\", b"\\")
    findings = []
    if LOCAL_PATH.search(normalized):
        findings.append("local-path")
    if CREDENTIAL.search(data):
        findings.append("credential")
    return findings


def scan_distribution(root: Path) -> list[tuple[str, str]]:
    """Return (relative file, finding type), without returning matched content."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("distribution root must be a directory")
    findings: list[tuple[str, str]] = []
    for file in sorted(root.rglob("*")):
        if file.is_symlink() or not file.is_file():
            continue
        relative = file.relative_to(root).as_posix()
        if file.suffix.lower() == ".zip":
            try:
                with ZipFile(file) as archive:
                    for entry in archive.infolist():
                        if Path(entry.filename).suffix.lower() not in TEXT_SUFFIXES:
                            continue
                        for kind in _text_findings(archive.read(entry)):
                            findings.append((relative, kind))
            except (BadZipFile, OSError):
                findings.append((relative, "invalid-zip"))
        elif file.suffix.lower() in TEXT_SUFFIXES or file.name.lower() in {".env", "credentials"}:
            try:
                data = file.read_bytes()
            except OSError:
                findings.append((relative, "unreadable"))
                continue
            findings.extend((relative, kind) for kind in _text_findings(data))
    return findings


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python scripts/audit_distribution.py <distribution-directory>", file=sys.stderr)
        return 2
    try:
        findings = scan_distribution(Path(args[0]))
    except (OSError, ValueError) as exc:
        print(f"distribution audit could not run: {type(exc).__name__}", file=sys.stderr)
        return 2
    if findings:
        counts: dict[str, int] = {}
        for _, kind in findings:
            counts[kind] = counts.get(kind, 0) + 1
        for kind, count in sorted(counts.items()):
            print(f"FAIL {kind}: count={count}")
        return 1
    print("PASS: distribution text and ZIP members contain no detected local paths or credentials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
