# 更新履歴

## 開発中 — Windows/macOS クロスプラットフォーム化

- Windows専用のKiCad探索をOS別にし、macOS KiCad 10アプリのCLI、シンボルライブラリ、GUI起動に対応。
- ngspiceは各OSのネイティブ実行ファイルだけを検出し、Windows実行ファイルをmacOSで誤実行しない。
- macOSの基板生成はKiCadと同じ版のpcbnewを読み込めるPythonをKICAD_PYTHONで指定し、版が一致しない場合は停止。
- macOS ARM64/IntelとWindowsのGitHub Actionsビルド、パッケージ構造・SHA-256検査を追加。
- macOSの署名・公証、物理MacでのGUI E2E、KiCad 10 pcbnew環境は未確認。CI実行結果はテストレポートを参照。

## v0.1.0-preview.1 — 2026-10-31

- CircuitDSL v1/v2検証、KiCad回路図生成、BOM、日本語診断、SVG、ERC/netlist連携。
- 明示指定に限った2層PCB生成とKiCad DRC連携。
- 限定RC過渡解析のngspice連携、任意OpenAI互換APIアダプター。
- Windows日本語Tk GUIとPyInstaller onedir配布版。
- KiCad 10.0.7でLEDサンプルをGUI保存/再読込し、ERC/DRCを検証。

これはプレビューです。自動配線、GNDゾーン、IPC連携、一般的なSPICEモデル解析、AI修正の自動適用、Hブリッジ安全設計、製造承認は未実装または未検証です。詳しくは [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) と [`reports/test-results.md`](reports/test-results.md) を参照してください。
