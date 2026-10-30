# CircuitDSL v2

CircuitDSL v2 は v1 の `project` / `design` / `nets` / `components` を保った拡張形式です。JSON は追加依存なしで読み込み、PyYAML がある場合は `safe_load` でYAMLを読みます。正式スキーマは [`schemas/circuit-v2.schema.json`](../schemas/circuit-v2.schema.json) です。

## v1との互換

- `parse_circuit()` は v1 と v2 の両方を受け付けます。
- v1の入力構造は変更せず、必要な場合だけ `migrate_v1_to_v2()` を明示的に使います。移行は既存フィールドをそのまま複製します。
- 未登録シンボルやカタログにないピン番号は両バージョンで拒否します。KiCadライブラリに同名シンボルがあっても、カタログとピン番号が一致しない部品は自動的に採用しません。

## v2の追加項目

- `metadata`: `author`、`revision`、`description`
- `power_rails`: ネットごとの公称/最小/最大電圧、電流制限。電圧範囲とネット参照を意味検査します。
- `safety_notes`: 人が確認する必要のある安全上の注意。解決済み扱いにはしません。
- `components[].properties`: 追加のスカラー部品属性
- `components[].placement`: 回路図シンボルの座標。現在は表面・回転0度のみです。
- `pcb`: 層数、明示した基板厚、矩形外形、クリアランス、最小配線幅、銅厚、温度上昇条件、配置、取付穴、明示配線
- `simulation`: 明示的なPULSE電源、過渡解析時間、観測ネット。現在は理想抵抗/コンデンサのみSPICEに変換し、コネクタはネット境界として無視します。他の部品はモデルを捏造せずBLOCKEDにします。
- `diagnostics`, `suggestions`: DSLに含めて運べる検証記録と提案。提案を自動適用しません。

PCB生成には `layers: 2`、`board_thickness_mm`、`outline`、正の `clearance_mm` / `trace_width_mm`、全参照番号の `pcb.placements` が必要です。`pcb.placements` は全参照番号に `x_mm` / `y_mm` を明示します。`pcb.routes` は各ネットの銅層 (`F.Cu` / `B.Cu`)、任意の配線幅、2点以上の座標列を指定します。配線点や最小幅は意味検査し、部品パッドとの導通、短絡、クリアランス等はKiCad DRCでも検査します。配線を省略したネットは未配線として扱います。

## 例

[`samples/led_v2.circuit.yaml`](../samples/led_v2.circuit.yaml) は入力コネクタ、抵抗、LEDを使う2層例です。標準フットプリントと全配置・配線を明記しています。これは小信号デモであり、モーター用電流設計の例ではありません。

[`samples/LED_Indicator_v2/`](../samples/LED_Indicator_v2/) に、そのDSLから生成しKiCad 10.0.7で保存/再読込まで確認したネイティブプロジェクトとERC/DRC/netlistレポートを含めています。製造可能性は `NOT_PROVEN` です。

`samples/hbridge_incomplete.circuit.yaml` は v1 のまま維持しています。停止電流や高側ゲート駆動等が不足するため、回路図/PCB出力をBLOCKEDにします。

### SPICE transient

[`samples/rc_filter_spice_v2.circuit.yaml`](../samples/rc_filter_spice_v2.circuit.yaml) を参照してください。`simulation.analysis` は現在 `transient` のみです。正の `step_s` / `stop_s`、PULSE sourceの電圧/時間条件、`observe_nets` を必須とします。SPICEノード名はネット名から自動生成し、式/コマンド挿入を避けます。指定された抵抗値・容量値を理想モデルとして使い、値の単位はΩ/Fまたは単位なし数値に限定します。

SPICE実行時は `ngspice -n -b` を使い、ユーザーの `.spiceinit` は読み込みません。`wrdata` 以外の制御コマンド、外部シェル/スクリプト、ネットリストフォルダー外のモデル参照/出力、既存CSVの上書きは拒否します。実部品の公差・寄生・温度はモデル化しないため、シミュレーション結果を実機保証に使わないでください。

## 現在の実装境界

- 回路図は単一A3シート15部品までです。階層シート、階層ピン、電源シンボルの自動配置、シンボル回転は未対応です。
- KiCad標準シンボル/フットプリントの利用可能なものはKiCad 10インストールから読み込み、型番/ピン番号をカタログと比較します。カタログにないシンボルを推測しません。
- PCB生成はKiCad同梱PythonのKiCad 10 `pcbnew` に依存します。矩形2層ボード、明示配置、明示直線配線、KiCad DRCまでです。board thicknessを仮定しません。自動配置、オートルーター、ゾーン/GNDプレーン、取付穴生成、3Dレンダリングは未対応です。
- `ROUTED` は指定ネットのパッドを明示配線グラフで接続した状態です。KiCad DRCの結果は別に報告します。製造判定は電流容量/熱/実装条件の検証がないため `NOT_PROVEN` のままです。DRCに違反、または未配線があれば `NOT_MANUFACTURABLE` とします。
- `diagnostics` と `suggestions` は入力データとして検査しますが、診断は毎回現在のDSLから再計算し、提案の自動適用/差分ロールバックはしません。
- 現在の実装は複数階層シート、IPC接続、非RC SPICEモデル、AC/DC解析、AI自動修正を実装していません。
