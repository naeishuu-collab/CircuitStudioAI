# テスト・実機検証結果

実施日: 2026-10-30。成功/失敗は実際に実行した項目だけを記載します。

## 自動テスト

| コマンド/操作 | 環境 | 結果 |
|---|---|---|
| `py -3 -m compileall -q app.py circuitstudio tests` | Python 3.13.15 | PASSED, exit 0 |
| `py -3 -m unittest discover -v` | Python 3.13.15 | PASSED: 37 tests, 37 passed, 0 failed, 0 skipped |
| `py -3.11 -m compileall -q app.py circuitstudio tests` | Python 3.11.9 | PASSED, exit 0 |
| `py -3.11 -m unittest discover -v` | Python 3.11.9 | PASSED: 37 tests, 36 passed, 0 failed, 1 skipped; optional `jsonschema` is not installed in this interpreter |
| Tk GUI作成/更新/終了 smoke | Python 3.11.9 | PASSED, `CircuitStudioApp` root initialized |
| `build-windows.bat` | Windows 11, Python 3.11.9, PyInstaller 6.22.3 | PASSED, onedir配布物を生成 |
| 配布版 `CircuitStudioAI.exe` 起動・GUI表示・正常終了 | Windows 11 | PASSED, 日本語ウィンドウ表示、終了コード0 |
| 配布版GUIからv2 LEDサンプルをKiCad/PCB出力 | Windows 11, KiCad 10.0.7 | PASSED, schematic/netlist/SVG/BOM/PCBを生成、ERC 0件、DRC 0件、未配線0。初回に検出した凍結配布物の`pcbnew_adapter.py`欠落をspecに追加して再ビルド後に再実行 |
| 配布版GUIから既存LED PCBを評価しJSON保存 | Windows 11, KiCad 10.0.7 | PASSED, DRC違反0、未配線0。原本PCBへの書き込みなし。結果は一時フォルダーに保存 |
| 配布版GUIからngspice RC transientを実行 | Windows 11, ngspice 47 | PASSED, 547データ行。配布物内サンプルでは隣に同名CSVがあり上書きを安全にBLOCKED。一時フォルダーのコピーで再実行 |
| KiCad 10 GUIで生成schematicを開き、隔離コピーで保存・終了・再読込 | Windows 11, KiCad 10.0.7 | PASSED。初回保存時の旧フォーマット変換通知を確認し、変換した一時コピーを閉じて再読込 |
| 変換後回路図のERC/netlist/SVG | Windows 11, KiCad 10.0.7 | PASSED。ERC 0違反、netlistは`J1.1/R1.1=VCC`、`R1.2/D1.2=LED_A`、`D1.1/J1.2=GND`を確認、SVG 1枚 |
| KiCad 10 PCBエディターで生成boardを開き、隔離コピーで保存・終了・再読込 | Windows 11, KiCad 10.0.7 | PASSED。3 footprintとF.Cu/B.Cu配線を表示。保存後に同じboardを再読込 |
| 保存・再読込後PCBのDRC | Windows 11, KiCad 10.0.7 | PASSED, 0違反 / 0未配線 |

37件にはDSL構文/移行、スキーマ、意味検査、未知シンボル/ピン、ネット接続、電気診断、PCB、KiCad統合、SPICE入力制限とngspice実行を含みます。Python 3.11の1件skipは任意依存 `jsonschema` の不在です。

## KiCad 10.0.7 CLI

| 対象 | 結果 |
|---|---|
| `kicad-cli version` | `10.0.7` |
| LED回路図/ERC | PASS, 0 error / 0 warning / 0 exclusion |
| LED回路図ネットリスト | PASS, `VCC`, `LED_A`, `GND` のピン接続を確認 |
| LED回路図SVG | PASS |
| LED PCB DRC | PASS, 0違反 / 0未配線 |
| CircuitDSL v2 LED生成プロジェクト | ERC 0件、netlist/SVG成功、3 footprints / 8 trace segments、DRC 0件 / 0未配線 |
| 既存LEDサンプルの一時コピー検証 | ERC/netlist/SVG/DRCに成功。元ファイルは維持 |

KiCad本体での回路図/PCB GUIオープン・隔離コピーの保存・閉じて再読込を確認しました。初回回路図保存時は旧フォーマット変換通知が出ており、KiCad 10形式への変換はユーザーが保存した場合に行われます。変換後ERCとPCB DRCはいずれも0件です。3D表示、別PCでの再現はNOT EXECUTEDです。

## ngspice

OS PATHへの導入はしていません。公式Windows 64-bit ngspice 47の実行ファイルを `tools/ngspice-47/` に隔離し、公式配布のSHA-256 `59225971bd68cdd1199443649aa4615a9e6d684933f205ab49006a3942518f5a` と照合しました。CircuitDSL RC例を実行し、ngspice-47が0終了コード、547データ行の過渡解析CSVを返すことを確認しました。シミュレーションデッキ/モデルは明記された理想R/CとPULSE電源です。

## 未実行

- KiCad GUIでの回路図/PCBオープン/隔離コピー保存/閉じて再読込: PASSED。3D表示、別PC再現: NOT EXECUTED
- IPC API接続/文書操作: NOT EXECUTED / KiCad 10回路図操作は対象外
- OpenAI互換API: NOT EXECUTED (外部API/課金なし)
- モーター実機、電源投入、熱、EMC、製造試験: NOT EXECUTED
- 3D出力、オートルート、GNDゾーン: NOT IMPLEMENTED
- GUI全ボタンの網羅、既存PCBのGUI視覚プレビュー、EXE別PC確認: NOT EXECUTED

## 実行環境

Windows 11 Home build 26200、AMD Ryzen AI 7 350、RAM 29.8 GiB、Python 3.13.15 / 3.11.9、KiCad 10.0.7、ngspice 47 (project-local)。環境の詳細と制限は [`kicad10-environment-audit.md`](kicad10-environment-audit.md) を参照してください。

## サンプルの判定

- `samples/LED_Indicator/`: KiCad CLI ERC/DRC PASSの小信号デモ。製造判定は電流/熱等を評価していないため `NOT_PROVEN`。
- `samples/LED_Indicator_v2/`: CircuitDSL v2から生成したKiCadネイティブプロジェクト。KiCad 10.0.7 GUI保存/再読込、ERC 0件、VCC/LED_A/GND netlist一致、DRC 0件/未配線0を確認。製造判定は `NOT_PROVEN`。
- `samples/RC_Filter_SPICE/`: KiCad出力と実ngspice RC過渡CSVを保存。指定した理想モデル内の解析成功であり、実機保証ではありません。
- `samples/hbridge_incomplete.circuit.yaml`: モーター停止/起動電流、MOSFET/ドライバ、保護、熱等が未確定でBLOCKED。安全なHブリッジ完成品ではありません。


## 公開前ベースライン再実行（2026-10-30）

| コマンド | Python | 結果 | 生ログ |
|---|---|---|---|
| `py -3.13 -m compileall -q app.py circuitstudio tests` | 3.13.15 | PASSED, exit 0 | `baseline-python313-20261030.log`（ローカル用、公開除外） |
| `py -3.13 -m unittest discover -v` | 3.13.15 | PASSED, 37成功/0失敗/0スキップ | 同上 |
| `py -3.11 -m compileall -q app.py circuitstudio tests` | 3.11.9 | PASSED, exit 0 | `baseline-python311-20261030.log`（ローカル用、公開除外） |
| `py -3.11 -m unittest discover -v` | 3.11.9 | PASSED, 36成功/0失敗/1スキップ（jsonschema未導入） | 同上 |

ログ保存先は`reports/`です。テストは両ランタイムで実際に実行し、exit 0でした。生成netlist XML内の絶対ユーザーパスは公開前監査で検出され、`.gitignore`により除外します。


## Windows配布パッケージ再検証（2026-10-31）

| 項目 | 結果 |
|---|---|
| PyInstaller隔離ビルド | Python 3.11.9 / PyInstaller 6.22.3、`CircuitStudioAI.spec`、exit 0 |
| 内部サンプル | CircuitDSL 6ファイルのみ。KiCad/CSV/XMLなどのプロジェクト資料は内部データから除外 |
| Windowsパッケージ用サンプルフィルター | PowerShellで42ファイルを一時コピーし、netlist XML、`.kicad_prl`、lock、log、backupsが含まれないことを確認 |
| Release ZIP | 1,113ファイル。ZIP CRC、危険なパス名の検査、隔離先への全展開・各ファイルSHA-256一致: PASS |
| 配布物プライバシー走査 | テキスト成果物でユーザープロファイル絶対パス0件、認証情報パターン0件 |
| Release ZIP SHA-256 | 同梱の`.zip.sha256`に記録 |
| 生成した新EXEのGUI E2E | NOT EXECUTED。この再梱包でのKiCad/GUI操作は未確認。前回配布版GUI E2Eは上記の通りPASS |
| `build-windows.bat`全体の再実行 | NOT EXECUTED。既存`dist`を保護する停止条件があるため、隔離PyInstallerビルドとパッケージフィルターを個別に検証 |

公開前のテキスト監査では、ユーザーパスを含む生成netlist XML 10件を特定しました。これらは`.gitignore`、PyInstallerの内部データ選択、Windowsパッケージのサンプルフィルターで公開物から除外します。プロジェクト固有LICENSEは未設定のままとし、第三者コンポーネント通知とライセンスファイルを配布物へ同梱します。


## GitHub公開結果（2026-10-31）

- Public repository: https://github.com/naeishuu-collab/CircuitStudioAI
- Prerelease: https://github.com/naeishuu-collab/CircuitStudioAI/releases/tag/v0.1.0-preview.1
- ZIP: `CircuitStudioAI-Windows-x64-v0.1.0-preview.1.zip` (26,493,064 bytes)
- SHA-256: `744e9934b2e205fad8708951cae25ae34a0c1629ab8b2ae464d3a7e7aee8c2fa`
- GitHubからRelease assetsを取得し、同梱checksumと再計算値が一致することを確認しました。公開先はPUBLIC、Releaseはprerelease、draftではありません。
