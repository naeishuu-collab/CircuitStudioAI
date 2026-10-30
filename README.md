# CircuitStudio AI

Windows向けのKiCad 10回路設計支援プロトタイプです。CircuitDSL v1/v2を検証してKiCad回路図を作り、KiCad CLIのERC・ネットリスト・SVGを実行します。v2で明示フットプリント、配置、矩形外形、配線を指定した場合は2層PCBを生成し、KiCad DRCを実行します。

## 起動

Python 3.10以上とTkが必要です。

```powershell
py -3 app.py
```

`run.bat` からも起動できます。手動CircuitDSL、KiCad出力、診断はAPIキーなしで使えます。完全なYAML文法にはPyYAMLが必要ですが、同梱JSON形式のサンプルには追加依存がありません。

Windows配布版は [`build-windows.bat`](build-windows.bat) でビルドします。出力は `dist/CircuitStudioAI/CircuitStudioAI.exe` です。EXEにはPython/Tkとサンプルを含み、KiCad本体は含みません。ビルドにはPython 3.11とPyInstallerが必要です。KiCad 10は回路図/PCBのネイティブ検査に必要です。

## サンプル

- `samples/led.circuit.yaml`: CircuitDSL v1 LED回路
- `samples/led_v2.circuit.yaml`: コネクター付きLED回路、KiCad 10 ERC 0件、2層PCB明示配線の基準例
- `samples/LED_Indicator_v2/`: 上記DSLから作成し、KiCad 10 GUI保存/再読込、ERC/netlist、PCB DRCを確認したネイティブプロジェクト
- `samples/rc_filter.circuit.yaml`: RCローパス回路
- `samples/mosfet_switch_unverified.circuit.yaml`: 未選定MOSFETのローサイド構造例。部品定格不足をUNKNOWNで報告
- `samples/hbridge_incomplete.circuit.yaml`: 条件不足のHブリッジ。安全条件未確定のため出力をBLOCKED

## 機能と制限

- CircuitDSL v1/v2の構文・スキーマ・意味検査、明示的シンボル/ピン照合、ネットグラフ、保守的な電気診断
- KiCad 10標準シンボルの埋め込み回路図生成、BOM、日本語診断、ERC、ネットリスト、SVG
- KiCad同梱 `pcbnew` を使う限定2層PCB生成。2層/基板厚/外形/制約/全フットプリント/配置/配線をDSLに明示します。オートルーター、ゾーン、取付穴、裏面配置、3D生成は未対応です
- PCB DRC PASSは電流容量、温度上昇、安全性、実装品質を証明しないため、製造判定は `NOT_PROVEN` のままです
- CircuitDSL v2で明示した理想R/Cの過渡解析デッキを生成します。ngspice 47を別実行ファイルとして利用し、実行時はCSVを出力します。その他の部品モデルやAC解析は未対応です
- 任意のOpenAI互換APIにDSL案生成を依頼できます。APIキーなしでも手動DSLは利用可能です。AI修正の自動適用/差分ロールバックは未実装です
- KiCad IPC APIはKiCad 10ではPCBエディターの実行中GUI連携向けです。CircuitStudioのIPC操作は未実装で、回路図/CLI検査は公式CLIとネイティブファイル経路を使います
- KiCad 10.0.7でLED回路図とPCBをGUI表示し、隔離コピーを保存・終了・再読込。変換後ERC/DRCは0件、未配線0です。回路図初回保存時に形式変換通知があります。3D表示は未検証、階層回路は未対応です
- 15部品を超える階層/複数シートは未対応です

## テスト

```powershell
py -3 -m unittest discover -v
py -3.11 -m unittest discover -v
```

KiCad CLIがあれば実機統合テストを行い、なければ該当テストをskipします。現環境での実測結果とKiCad 10互換性は [`reports/test-results.md`](reports/test-results.md)、環境調査は [`reports/kicad10-environment-audit.md`](reports/kicad10-environment-audit.md)、DSL v2仕様は [`docs/CircuitDSL-v2.md`](docs/CircuitDSL-v2.md) を参照してください。

出力 `.kicad_sch` / `.kicad_pcb` はKiCad GUIで開いて目視確認してください。ERC/DRC PASSは実機動作・安全・製造承認ではありません。


## インストール・利用許諾

Windows配布版とソース実行手順は [`INSTALL.md`](INSTALL.md)、開発手順は [`CONTRIBUTING.md`](CONTRIBUTING.md)、プレビュー内容は [`CHANGELOG.md`](CHANGELOG.md) を参照してください。

CircuitStudio固有の `LICENSE` は未設定です。この公開は再配布・改変許諾を示しません。第三者コンポーネントの条件は [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) を確認してください。
