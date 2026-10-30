# Windows 11 インストール・起動ガイド

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

## 最初の操作

- DSL例を開く: `samples\led_v2.circuit.yaml`
- Hブリッジ診断を見る: `samples\hbridge_incomplete.circuit.yaml`。電流、ドライバ、熱などが未指定なのでBLOCKEDになります。完成設計として通電しないでください。
- 画面の「CircuitDSLを開く」でDSLを読み込み、「検証/生成」から出力先を選びます。検査結果・日本語レポート・BOMとKiCadネイティブファイルが出力されます。
- KiCad GUIで回路図と基板を開き、視覚的にも確認してください。ERC/DRCの合格だけで安全性や製造可能性は保証されません。

詳しい画面操作と各診断項目は [`docs/ユーザーマニュアル.md`](docs/ユーザーマニュアル.md) を参照してください。

## ライセンスと第三者コンポーネント

このリポジトリにはCircuitStudio固有の `LICENSE` を設定していません。公開は再配布・改変許諾を意味しません。ngspice、PyInstaller、KiCad、Python/Tcl/Tkの通知は [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) を参照してください。
