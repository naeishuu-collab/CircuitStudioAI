# Windows / macOS インストール・起動ガイド

## 配布版を使う

1. GitHub Releasesから `CircuitStudioAI-Windows-x64-v0.1.0-preview.1.zip` をダウンロードして展開します。
2. ZIPと同じReleaseに掲載されたSHA-256と照合します（PowerShell）。

   ```powershell
   Get-FileHash .\CircuitStudioAI-Windows-x64-v0.1.0-preview.1.zip -Algorithm SHA256
   ```

3. 展開先の `CircuitStudioAI\CircuitStudioAI.exe` を起動します。Pythonは不要です。
4. 回路図/PCBの実機検査にはKiCad 10を別途インストールしてください。KiCadのCLIを自動検出できない場合、アプリのKiCad CLI設定で `kicad-cli.exe` のフルパスを指定します。
5. SPICE解析は配布物内のngspice 47を使います。解析モデルが不足する回路は実行せず、未実行として報告します。

WindowsのSmartScreenが表示された場合は、発行元未署名の配布物として扱い、Releaseのハッシュと配布元を確認してください。保護機能を無効にする必要はありません。

## macOS 15以降

macOS版はMac上でビルドします。GitHub Actionsの [Cross-platform CI](https://github.com/naeishuu-collab/CircuitStudioAI/actions/workflows/cross-platform.yml) から成功した実行を開き、`CircuitStudioAI-macOS-arm64`（Apple Silicon）または `CircuitStudioAI-macOS-x64`（Intel）のArtifactをダウンロードします。ZIPにはアプリ、マニュアル、第三者通知が入り、DMGも同梱されます。SHA-256は `SHA256SUMS-macos-<arch>.txt` を使って確認してください。

1. DMGを開き、`CircuitStudioAI-macOS-<arch>.app`をアプリケーションフォルダーまたは自分のユーザーフォルダーへコピーします。
2. 配布物はDeveloper ID署名・Apple公証をしていません。まず配布元とSHA-256を確認し、FinderでアプリをControlクリックして「開く」を選びます。macOSが保留した場合は「システム設定 → プライバシーとセキュリティ」に表示されたアプリ名を確認して「このまま開く」を選んでください。Gatekeeperを無効化しないでください。
3. KiCad本体は含まれません。KiCad 10を別途インストールしてください。CLIは通常 `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` にあります。自動検出されない場合、ターミナルから `KICAD_CLI` にCLIのフルパスを設定して起動します。
4. 回路図・ERC・netlist・SVG・PCB DRCはKiCad CLIを使います。PCB生成にはKiCadと同じバージョンの `pcbnew` を読み込めるPython実行環境が必要です。バージョン一致を確認したうえで `KICAD_PYTHON` を設定します。

   ```sh
   /path/to/python3 -c 'import pcbnew; print(pcbnew.GetBuildVersion())'
   /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli version
   KICAD_CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli KICAD_PYTHON=/path/to/python3 /Applications/CircuitStudioAI-macOS-arm64.app/Contents/MacOS/CircuitStudioAI
   ```

   2つのバージョンが一致しない場合や `pcbnew` を読み込めない場合、基板生成は `NOT_EXECUTED` になります。KiCad 10の `pcbnew` は将来のKiCadで削除予定の旧APIです。
5. ngspiceはmacOSアプリに含めていません。必要ならmacOS向けngspiceを別途用意し、ターミナル起動時の `PATH` または `NGSPICE` で指定してください。

CIはGitHubのmacOS 15 runnerでアプリのビルド・CLI連携・パッケージ展開を検査します。macOS 15より前のOS、署名・公証、物理MacでのGUI操作はこの検査に含まれません。KiCad 10本体は別途必要です。

## ソースから起動する

Python 3.11または3.13を用意し、プロジェクトのルートで実行します。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

追加のYAML記法を扱う場合のみ `python -m pip install PyYAML` を実行してください。JSON形式のCircuitDSLサンプルとGUIの手動入力は、APIキーなしで使えます。ngspiceがないソース環境ではSPICE機能は未実行になります。外部ngspiceはPATHまたは `NGSPICE` 環境変数に指定できます。

## テスト・EXEビルド

```powershell
py -3.11 -m unittest discover -v
.\build-windows.bat
```

ビルドにはPyInstaller 6.22.3が必要です（`python -m pip install -r requirements-build.txt`）。出力は `dist\CircuitStudioAI\CircuitStudioAI.exe` です。KiCad本体は同梱しません。

## macOSアプリのビルド

macOSホストでPython 3.11とTkが利用可能な状態で実行します。IntelとApple Siliconはそれぞれのアーキテクチャ上でビルドしてください。

```sh
python3 -m venv .venv
source .venv/bin/activate
bash scripts/build_macos.sh
```

出力は `dist/CircuitStudioAI-macOS-<arm64|x64>.zip`、`.dmg`、SHA-256一覧です。既存の同名出力がある場合は上書きせず停止します。Mac用バイナリをWindowsで作成することはできません。

## 最初の操作

- DSL例を開く: `samples\led_v2.circuit.yaml`
- Hブリッジ診断を見る: `samples\hbridge_incomplete.circuit.yaml`。電流、ドライバ、熱などが未指定なのでBLOCKEDになります。完成設計として通電しないでください。
- 画面の「CircuitDSLを開く」でDSLを読み込み、「検証/生成」から出力先を選びます。検査結果・日本語レポート・BOMとKiCadネイティブファイルが出力されます。
- KiCad GUIで回路図と基板を開き、視覚的にも確認してください。ERC/DRCの合格だけで安全性や製造可能性は保証されません。

詳しい画面操作と各診断項目は [`docs/ユーザーマニュアル.md`](docs/ユーザーマニュアル.md) を参照してください。

## ライセンスと第三者コンポーネント

このリポジトリにはCircuitStudio固有の `LICENSE` を設定していません。公開は再配布・改変許諾を意味しません。ngspice、PyInstaller、KiCad、Python/Tcl/Tkの通知は [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) を参照してください。
