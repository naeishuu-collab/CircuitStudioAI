# Cross-platform implementation audit

Audit date: 2026-10-31. This file records measured state and must not be read as a macOS physical-device certification.

## Repository and preservation

- Repository remote: `naeishuu-collab/CircuitStudioAI`
- Starting branch/HEAD: `main` / `c3346ad1f53e0e556aefdcc2c5c588d6249bb68b`
- Starting worktree: clean; no uncommitted or untracked project files.
- Work branch: `feature/macos-cross-platform`, created from the recorded HEAD.
- Existing prerelease `v0.1.0-preview.1` is read-only and unchanged.
- Pre-change archive: `CircuitStudioAI-pre-macos-20261031-005838Z.zip`, stored outside the repository beside the workspace. SHA-256: `3317325a5e5581598cd4acb204acaa576fd64d17feded1c3f9e0e1bc53a771b4`. A 2,614-file isolated restore was compared by SHA-256 and passed.

## Local Windows baseline

| Item | Measured value |
|---|---|
| OS | Windows 11 Home 64-bit, build 26200 |
| CPU / memory | AMD Ryzen AI 7 350, 8 cores / 16 threads; 29.8 GiB RAM |
| Python | 3.11.9 and 3.13.15 |
| Git | 2.55.0.windows.5 |
| KiCad | 10.0.7, installed under the standard Program Files tree |
| CLI | Not on PATH; the installed `kicad-cli.exe` runs and reports 10.0.7 |
| pcbnew | KiCad-bundled Python imports `pcbnew`; `GetBuildVersion()` reports 10.0.7 |
| ngspice | Local Windows ngspice 47 bundle exists; it is ignored by Git and is not committed |

Before code changes, `compileall` and `python -m unittest discover -v` passed on Python 3.13 (37 tests) and 3.11 (37 tests, one optional-dependency skip). Logs are local/ignored; the test report records the command and counts.

## macOS build and KiCad boundary

This development host is Windows and cannot produce or launch a native macOS app. GitHub Actions is configured to build on standard `macos-15` ARM64 and `macos-15-intel` runners. The project targets macOS 15+ builds; older OS versions and a physical Mac remain unverified until separately tested.

KiCad's macOS download page currently lists KiCad 10.0.7 and macOS 12 or newer. The CLI documentation gives the app-bundle CLI location under `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`. This project detects that path, resolves symbols from the app's SharedSupport directory, and opens files through macOS `open -a`. The workflow installs KiCad on the runner and fails if the detected CLI is not KiCad 10.x.

KiCad's documentation marks the SWIG `pcbnew` bindings deprecated since KiCad 9, with planned removal in KiCad 11. On macOS, PCB generation is therefore fail-closed: it requires an explicit `KICAD_PYTHON`, imports `pcbnew`, and compares its build version with `kicad-cli version`. A missing or mismatched runtime returns `NOT_EXECUTED`. The Mac ABI itself is not claimed compatible.

KiCad IPC supports macOS and Windows, but the application does not implement an IPC client. Schematic generation and DRC/ERC checks use native files and the CLI. SPICE on Mac requires an external native ngspice; no Windows binary is shipped in the Mac artifact.

## Build and release policy

PyInstaller's official spec supports a macOS `BUNDLE`; the Mac script runs on Mac, creates a DMG and ZIP, extracts and checks the app structure, and emits SHA-256 checksums. Artifacts are CI outputs only. They are unsigned and unnotarized. The existing v0.1.0 prerelease is not replaced; a new prerelease is withheld until platform validation is sufficient.

References:

- [KiCad 10 CLI manual](https://docs.kicad.org/10.0/en/cli/cli.html)
- [KiCad macOS downloads](https://www.kicad.org/download/macos/)
- [KiCad pcbnew Python bindings and deprecation](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/)
- [KiCad IPC API](https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/)
- [PyInstaller spec files](https://pyinstaller.org/en/latest/spec-files.html)
- [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
