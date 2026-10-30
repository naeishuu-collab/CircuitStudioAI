# CircuitStudio AI 実装状況

最終更新: 2026-10-30。状態は実装/実行した範囲を区別しています。

| 領域 | 状態 | 根拠・制限 |
|---|---|---|
| Windows/KiCad環境 | VERIFIED | Windows 11、KiCad 10.0.7、CLI、標準ライブラリ、KiCad同梱 `pcbnew` を実測。ngspice 47は公式配布を検証してプロジェクト内に配置。詳細は環境監査を参照 |
| CircuitDSL v1 | IMPLEMENTED / TESTED | 既存形式維持、JSON/YAML解析、スキーマ/意味検査、v1サンプル互換 |
| CircuitDSL v2 | IMPLEMENTED / TESTED | versioned schema、電源レール、定格/制約、部品/ピン/ネット参照、PCB条件、simulation指定、診断情報。v1 migrationあり。階層/複数シートは未実装 |
| シンボル/ピン | PARTIAL | 登録カタログとKiCad標準ライブラリ定義を照合。未知型番/ピンは拒否。全KiCadシンボル・全部品型番の自動解決ではない |
| KiCad回路図/プロジェクト | VERIFIED (CLI + GUI ROUND-TRIP) | `samples/LED_Indicator_v2/` にKiCad 10.0.7のGUI保存/再読込まで確認したネイティブ例を保存。ERC/netlist/SVG、変換後ERC 0件とnet接続一致。初回保存時の形式変換通知あり。最大15部品/単一シート |
| PCB生成 | PARTIAL / NATIVE CLI + GUI VERIFIED | KiCad同梱 `pcbnew` で矩形2層・明示footprint/配置/直線配線を生成。LED例3 footprints、KiCad GUIで隔離コピー保存/再読込、保存後DRC 0件/未配線0。自動配置/配線、zone、取付穴生成、裏面配置、3Dなし。製造判定NOT_PROVEN |
| 電気診断 | PARTIAL | 抵抗損失、コンデンサ耐圧、MOSFET定格不足、Hブリッジ不足条件等。SOA、詳細スイッチング損失、温度/電流容量、実機動作は未評価 |
| 既存PCB評価 | VERIFIED (CLI + GUI E2E) | 基板構造とKiCad DRCを評価し、配布GUIから既存LED PCBのレポート保存も確認。高電流/リターン/放熱/配置のヒューリスティックは限定的 |
| SPICE | VERIFIED (RC transient) | CircuitDSLで明記した理想R/CとPULSE電源をngspice 47で解析、547行CSV。モデルのない部品、AC/DC/熱/実機寄生は未対応 |
| AI Provider | PARTIAL | 任意OpenAI互換API adapter。APIキーなし手動DSL利用可。今回は外部APIを呼び出していない。AIの修正差分自動適用/ロールバックは未実装 |
| 日本語GUI | PARTIAL / SELECTED FLOWS VERIFIED | 配布EXEの起動に加え、GUIからv2 LED回路図/PCB出力、既存PCBのDRC評価/JSON保存、ngspice RC実行を確認。KiCad GUIでschematic/PCB保存・再読込も確認。全ボタン、GUI内プレビューの視覚QA、3D、別PCは未検証 |
| KiCad IPC | NOT IMPLEMENTED | KiCad 10の対象範囲では回路図の稼働中編集は未対応。GUIドキュメント更新機能は実装していない |
| Windows EXE | BUILT / SELECTED GUI FLOWS VERIFIED | Python 3.11 + PyInstaller 6.22.3 onedir。起動に加え、LED生成、既存PCB評価、SPICE実行をE2E確認。EXE、Python/Tk、schema/sample/docs、ngspice実行ファイル、ライセンス資料を同梱。KiCad本体は別途必要 |

`STRUCTURE_READY_ELECTRICAL_REVIEW_REQUIRED` は構造検査の状態だけです。KiCad ERC/DRC PASS、SPICE成功、GUI起動は、電気安全・実機動作・熱設計・製造可能性の承認ではありません。

未実装/未検証項目の一覧、実コマンドと結果は [`../reports/test-results.md`](../reports/test-results.md) を参照してください。使い方は [`ユーザーマニュアル.md`](ユーザーマニュアル.md) を参照してください。
