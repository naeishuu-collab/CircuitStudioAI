# CircuitStudioAI v0.1.0-preview.1

## 含まれるもの

- Windows x64のPython同梱GUIアプリ（onedir ZIP）。
- CircuitDSL v1/v2の入力・検証と、KiCadネイティブ回路図/BOM/診断出力。
- 条件をすべて明示した限定的な2層PCB生成とDRC連携。
- 配布版内ngspice 47による、明示R/Cモデルの限定過渡解析。
- APIキーなしの手動CircuitDSL。外部AI APIは任意で、今回のテストでは呼び出していません。

## 検証

Windows 11、Python 3.11.9/3.13.15、KiCad 10.0.7。37テストはPython 3.13で37成功、Python 3.11で36成功・1スキップ（任意依存jsonschema未導入）。KiCad GUIの回路図/PCB保存・再読込、ERC、netlist、SVG、DRCをLEDサンプルで確認。テスト詳細は [`reports/test-results.md`](reports/test-results.md)。

## 制限

自動配置/配線、GNDゾーン、3D、IPC、全回路のSPICE、熱/SOA/EMC評価は未実装または未検証です。RP2040 Hブリッジ例は必要な電流・ドライバ・熱仕様が不足しておりBLOCKEDです。ERC/DRC PASSは安全性、実機動作、製造可能性を保証しません。

## ライセンス

CircuitStudio固有のLICENSEは含めていません。第三者通知はZIP内の `THIRD_PARTY_NOTICES.md` を確認してください。
