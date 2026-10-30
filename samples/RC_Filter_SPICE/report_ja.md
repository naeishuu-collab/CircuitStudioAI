# CircuitStudio AI — 検証レポート

- プロジェクト: RC_Filter_SPICE
- 設計意図: 5Vステップ入力のRCローパス。時定数は10kΩ×100nFで約1ms。
- 判定: 電気安全/製造適合の承認は未実施
- KiCad ERC: PASS
- KiCadネットリスト: PASS
- KiCad SVG: PASS
- SPICE: NOT_EXECUTED
- PCB生成: NOT_EXECUTED
- PCB DRC: NOT_EXECUTED
- 製造判定: NOT_PROVEN

## 診断

| 状態 | 重大度 | 検査ID | 対象 | 根拠 | 推奨 |
|---|---|---|---|---|---|
| UNKNOWN | warning | DESIGN_ASSUMPTION_UNKNOWN |  | 未確定条件: 実コンデンサのバイアス/温度特性は未評価 | 値を確認してDSLに反映してください。 |
| PASS | info | RESISTOR_POWER_RATING | R1 | 推定消費電力 0.0025 W、指定定格 0.1 W (P=I²R; 温度ディレーティング未考慮)。 | 抵抗値/電流/部品定格を見直し、周囲温度と実装条件で再評価してください。 |
| PASS | info | CAPACITOR_VOLTAGE_RATING | C1 | 供給電圧 5 V、コンデンサ指定耐圧 16 V。サージ/温度余裕は別途確認が必要です。 | DCバイアス、リップル、サージを含むデータシート条件を確認してください。 |
| PASS | info | POWER_GROUND_DECLARED |  | 電源ネット1個、GNDネット1個が部品ピンに割り当てられています。電流ループ/帰路は未証明です。 | KiCad ERC と実回路の帰路をレビューしてください。 |

## 制限

電気診断は明示されたDSL値に対する保守的な検査です。実機、安全動作領域、熱、EMC、電流容量、製造可能性を保証しません。

## SPICE実測

- エンジン: ngspice 47 (公式配布のSHA-256検証済み)
- 実行: transient / 理想抵抗・コンデンサ / 明示PULSE入力
- CSV: `transient.csv`
- 注意: 公差、温度、ESR、実デバイスの寄生成分はモデルに含まず、実機動作を保証しません。
