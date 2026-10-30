# KiCad 10環境監査

実測日時: 2026-10-30 (ローカル時刻)

## ホスト環境

| 項目 | 実測 |
|---|---|
| OS | Windows 11 Home 64-bit, build 26200 |
| CPU | AMD Ryzen AI 7 350 w/ Radeon 860M, 8 cores / 16 logical processors |
| RAM | 29.8 GiB |
| Python | `py -3` = 3.13.15、`py -3.11` = 3.11.9、Tk 8.6 |
| Node.js | v24.21.0 |
| Git | 2.55.0.windows.5。Git実行ファイルはあるが、この作業フォルダーに `.git` はなく、Git状態は取得不能 |
| KiCad | Registry `KiCad 10.0`、10.0.7、`C:\Program Files\KiCad\10.0` |
| KiCad PATH | PATHに含まれない。アプリは `KICAD_CLI`、PATH、標準Program Filesを探索 |
| KICAD_*環境変数 | 未設定 |
| ngspice | `ngspice` はPATHに存在せず、KiCadのDLLはCLIとして利用できない。今回、公式Windows 64-bit ngspice 47を検証後、プロジェクト内 `tools/ngspice-47/` に隔離。実解析確認はテストレポート参照 |

KiCadの `kicad-cli.exe`、`kicad.exe`、`eeschema.exe`、`pcbnew.exe`、同梱 `python.exe` はすべて存在します。CLI `version` 実行結果は `10.0.7` です。標準ライブラリは symbol 223ファイル、footprint 155 `.pretty` ディレクトリ、3D model 105ディレクトリを確認しました。

## Python / API

- Python 3.11.9 / 3.13.15 のどちらにも `pcbnew` と `kipy` はありません。
- KiCad同梱Pythonは3.11.5で、`import pcbnew` 成功、`pcbnew.GetBuildVersion()` は `10.0.7`。実装したPCB生成はこの同梱ランタイムを隔離した子プロセスとして使用します。
- IPC APIのPython client (`kipy`) は未導入です。KiCad IPCは実行中アプリを操作するAPIであるため、今回の既存ドキュメント検証には接続せず、CLI/ネイティブファイル方式を用いました。IPC接続は未実行です。
- KiCad公式文書はIPCによる稼働中KiCadへのリモート制御と、SWIG `pcbnew` の非推奨・KiCad 11削除予定を説明しています。PCB生成方式はKiCad 10限定の互換アダプターで、将来IPCへ置換が必要です。[CLI 10.0文書](https://docs.kicad.org/10.0/en/cli/cli.html)、[IPC API](https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/index.html)、[pcbnew Python bindings](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/index.html)

## KiCad CLI確認

KiCad 10.0.7上で `sch erc --format json --severity-all`、`sch export netlist --format kicadxml`、`sch export svg`、`pcb drc --format json --severity-all` を実行しました。これらのフラグは実機のCLIで確認したもので、任意のCLI出力は日本語Windowsの標準コードページに依存しないようUTF-8置換デコードします。

生成した回路図/基板の実機CLI結果と件数は [`reports/test-results.md`](test-results.md) に記録します。CLIはKiCadのGUI読み込み/保存/再読込や実機動作を証明しません。

## パス・権限

作業ディレクトリはOneDrive配下で、ディレクトリはreparse pointです。標準ユーザー権限でKiCad CLIと同梱Pythonを起動できました。管理者権限、システム設定変更、KiCad本体の変更、PATH/環境変数変更、ライブラリ追加は行っていません。ファイルACL全体と別ユーザー権限での動作は未確認です。

## API/GUI未検証

- CircuitStudio GUIと配布EXEの起動に加え、GUIからLED出力/既存PCB DRC評価/SPICE実行を確認済みです。KiCad 10.0.7 GUIで生成schematic/PCBの隔離コピーを保存・再読込し、ERC/DRC 0件を確認しました。GUIボタン全体、GUI内プレビュー視覚QA、3DはNOT EXECUTEDです。初回回路図保存時には旧形式変換通知があります。
- IPC APIは未接続です。実行中KiCad文書の同一性/未保存編集を扱う機能は実装していません。

## ngspice取得・互換性

- 公式配布のWindows 64-bit ngspice 47をプロジェクト内に展開し、SHA-256 `59225971bd68cdd1199443649aa4615a9e6d684933f205ab49006a3942518f5a` を配布元記載値と照合しました。ソース/バイナリとライセンスは `tools/ngspice-47/` に保持しています。
- OS全体のインストール、PATH変更、管理者権限は使っていません。RCサンプルのtransient解析とCSV生成を実行確認しました。詳細は [`test-results.md`](test-results.md) を参照してください。
