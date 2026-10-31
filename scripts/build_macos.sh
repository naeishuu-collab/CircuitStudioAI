#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macOS packaging must run on a macOS host." >&2
  exit 2
fi

host_arch="$(uname -m)"
case "$host_arch" in
  arm64) arch="arm64" ;;
  x86_64) arch="x64" ;;
  *) echo "Unsupported macOS architecture: $host_arch" >&2; exit 2 ;;
esac

dist="$ROOT/dist"
app="$dist/CircuitStudioAI.app"
package="$dist/CircuitStudioAI-macOS-$arch"
zip="$dist/CircuitStudioAI-macOS-$arch.zip"
dmg="$dist/CircuitStudioAI-macOS-$arch.dmg"
if [[ -e "$app" || -e "$package" || -e "$zip" || -e "$dmg" ]]; then
  echo "Existing build output is preserved; move it yourself before rebuilding." >&2
  exit 2
fi
mkdir -p "$dist"

python -c 'import tkinter; print("Tk", tkinter.TkVersion)'
python -m pip install --disable-pip-version-check -r requirements-build.txt
work="$(mktemp -d "${TMPDIR:-/tmp}/circuitstudio-pyinstaller.XXXXXX")"
python -m PyInstaller --clean --noconfirm --distpath "$dist" --workpath "$work" CircuitStudioAI.spec

if [[ ! -d "$app" ]]; then
  echo "PyInstaller did not create CircuitStudioAI.app." >&2
  exit 1
fi
info="$app/Contents/Info.plist"
plutil -lint "$info"
executable="$(/usr/libexec/PlistBuddy -c 'Print CFBundleExecutable' "$info")"
test -x "$app/Contents/MacOS/$executable"
find "$app/Contents" -type f -path '*/schemas/circuit.schema.json' -print -quit | grep -q .
find "$app/Contents" -type f -name 'led_v2.circuit.yaml' -print -quit | grep -q .

mkdir "$package"
ditto "$app" "$package/CircuitStudioAI-macOS-$arch.app"
cp README.md INSTALL.md CHANGELOG.md THIRD_PARTY_NOTICES.md "$package/"
cp docs/ユーザーマニュアル.md "$package/"

ditto -c -k --keepParent --sequesterRsrc "$package" "$zip"
unzip -t "$zip"
extract="$(mktemp -d "${TMPDIR:-/tmp}/circuitstudio-package-check.XXXXXX")"
ditto -x -k "$zip" "$extract"
restored="$extract/$(basename "$package")/CircuitStudioAI-macOS-$arch.app"
plutil -lint "$restored/Contents/Info.plist"
test -x "$restored/Contents/MacOS/$executable"
open -a "$restored"
sleep 5
app_pid="$(pgrep -x "$executable" | head -n 1 || true)"
if [[ -z "$app_pid" ]]; then
  echo "Extracted app did not stay running after launch." >&2
  exit 1
fi
kill -TERM "$app_pid"
for _ in {1..10}; do
  kill -0 "$app_pid" 2>/dev/null || break
  sleep 1
done
kill -KILL "$app_pid" 2>/dev/null || true
echo "Extracted macOS app launch smoke passed (bundle executable: $executable)."

hdiutil create -volname "CircuitStudioAI macOS $arch" -srcfolder "$package" -format UDZO "$dmg"
hdiutil imageinfo "$dmg" >/dev/null
mount="$(mktemp -d "${TMPDIR:-/tmp}/circuitstudio-dmg-check.XXXXXX")"
hdiutil attach "$dmg" -readonly -nobrowse -mountpoint "$mount" >/dev/null
plutil -lint "$mount/CircuitStudioAI-macOS-$arch.app/Contents/Info.plist"
test -f "$mount/THIRD_PARTY_NOTICES.md"
hdiutil detach "$mount" >/dev/null
(cd "$dist" && shasum -a 256 "$(basename "$zip")" "$(basename "$dmg")") > "$dist/SHA256SUMS-macos-$arch.txt"
echo "Created and inspected:"
printf '%s\n' "$zip" "$dmg" "$dist/SHA256SUMS-macos-$arch.txt"
