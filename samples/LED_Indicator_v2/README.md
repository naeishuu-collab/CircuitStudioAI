# LED_Indicator_v2

CircuitDSL v2から生成したKiCad 10.0.7確認用LEDプロジェクトです。

- `LED_Indicator_v2.kicad_pro` をKiCadで開くと回路図と基板を参照できます。
- `LED_Indicator_v2.circuit.yaml` が入力DSLです。
- `erc_report.json` は保存・再読込後のKiCad ERC結果です（違反0件）。
- `netlist.xml` でVCC、LED_A、GNDの端子接続を確認できます。
- `pcb_drc_report.json` は保存・再読込後のKiCad DRC結果です（違反0件、未配線0）。

これは小信号LEDの検証サンプルです。ERC/DRCの合格は、電源条件や部品定格を含む一般的な安全性、製造可能性を保証しません。製造判定は `NOT_PROVEN` です。
