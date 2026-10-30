# 開発への参加

変更は既存のCircuitDSL v1/v2、GUI、日本語文書、KiCad生成物との互換性を保ち、危険な電気設計をPASS扱いにしないでください。部品やピンの不明点は推測せずUNKNOWN/BLOCKEDにします。

## 開発・確認

- Python 3.11または3.13を使用します。
- `py -3.11 -m unittest discover -v` と `py -3.13 -m unittest discover -v` を実行します。
- KiCad CLIの実機テストを実行した場合、バージョン、コマンド、結果、未実行項目を `reports/test-results.md` に記録します。
- ngspiceにモデルがない場合、架空の波形や代替モデルで成功扱いしません。
- GUI、CLI、配布EXEのいずれを検証したかを明記します。

## コミット前

APIキーやローカル設定を追加しないでください。`.env`、`dist/`、バックアップ、KiCadの`.kicad_prl`、生成netlist XMLは`.gitignore`対象です。テストで作った絶対パスやユーザー情報を公開ファイルへ含めないでください。

CircuitStudio固有の `LICENSE` は現在未設定です。第三者コードやバイナリを追加・再配布する前に、その権利条件と通知要件を確認してください。
