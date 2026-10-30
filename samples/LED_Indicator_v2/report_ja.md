# CircuitStudio AI — 検証レポート

- プロジェクト: LED_Indicator_v2
- 設計意図: 5V入力から抵抗を介してLEDを点灯する。電流は約5mA。
- 判定: 電気安全/製造適合の承認は未実施
- KiCad ERC: PASS
- KiCadネットリスト: PASS
- KiCad SVG: PASS
- SPICE: NOT_EXECUTED
- PCB生成: ROUTED
- PCB DRC: PASS
- 製造判定: NOT_PROVEN

## 診断

| 状態 | 重大度 | 検査ID | 対象 | 根拠 | 推奨 |
|---|---|---|---|---|---|
| UNKNOWN | warning | DESIGN_ASSUMPTION_UNKNOWN |  | 未確定条件: LEDの型番と実際の順方向電圧は未確定 | 値を確認してDSLに反映してください。 |
| UNKNOWN | warning | SAFETY_NOTE_REVIEW |  | 安全上の注意: これは説明用の低電圧サンプルであり、実装前に実部品の定格を照合する。 | 注意事項を回路図、基板、部品仕様と照合してください。 |
| PASS | info | RESISTOR_POWER_RATING | R1 | 推定消費電力 0.025 W、指定定格 0.125 W (P=I²R; 温度ディレーティング未考慮)。 | 抵抗値/電流/部品定格を見直し、周囲温度と実装条件で再評価してください。 |
| PASS | info | POWER_GROUND_DECLARED |  | 電源ネット1個、GNDネット1個が部品ピンに割り当てられています。電流ループ/帰路は未証明です。 | KiCad ERC と実回路の帰路をレビューしてください。 |

## 制限

電気診断は明示されたDSL値に対する保守的な検査です。実機、安全動作領域、熱、EMC、電流容量、製造可能性を保証しません。
