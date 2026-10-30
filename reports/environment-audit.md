# 実行環境監査

実施日: 2026-10-30。以前の作業時点ではKiCad/ngspice未検出と記録されていましたが、今回対象PCを再監査し、以下の結果に更新しました。

| 項目 | 今回の実測 |
|---|---|
| OS | Windows 11 Home 64-bit, build 26200 |
| CPU / RAM | AMD Ryzen AI 7 350, 8C/16T / 約29.8 GiB |
| Python | 3.13.15 (`py -3`), 3.11.9 (`py -3.11`), Tk 8.6 |
| Node.js / Git | v24.21.0 / 2.55.0。作業フォルダーに `.git` はない |
| KiCad | 10.0.7, `C:\Program Files\KiCad\10.0`; `kicad-cli version` で確認 |
| KiCad tools/libs | kicad-cli, kicad.exe, eeschema.exe, pcbnew.exe、標準symbol/footprint/3Dライブラリ、KiCad同梱Python 3.11.5の `pcbnew` を確認 |
| Python IPC client | `kipy` は未導入。KiCad IPC接続未実施 |
| ngspice | OS PATHには不在。公式64-bit ngspice 47をSHA-256照合し、プロジェクト内 `tools/ngspice-47/` に展開。RC transient実行済み |
| 権限/環境変更 | 標準ユーザー権限で実行。KiCad、OS PATH、環境変数、システム全体の設定は変更していない |
| Git状態 | このプロジェクトはGitリポジトリではなく、Git status取得不能 |

KiCad 10 CLIの機能/結果、ngspice取得検証、GUI/IPCの未検証項目は [`kicad10-environment-audit.md`](kicad10-environment-audit.md) と [`test-results.md`](test-results.md) を参照してください。
