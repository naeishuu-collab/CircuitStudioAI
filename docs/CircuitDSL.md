# CircuitDSL v1

CircuitDSL v1 は `schemas/circuit.schema.json` をスキーマとする JSON/YAML データ形式です。JSON文書はYAML 1.2でも有効です。標準ライブラリだけの実行環境はこのJSON部分集合を受け付けます。PyYAMLを追加すると通常のYAML構文も安全ローダーで読みます。

v2 の追加項目と移行方法は [CircuitDSL v2仕様](CircuitDSL-v2.md) と [`schemas/circuit-v2.schema.json`](../schemas/circuit-v2.schema.json) を参照してください。v1は引き続き読み込み可能です。

## 項目

- `schema_version`: 現在は `1`
- `project`: `name`、任意の説明
- `design`: `intent`、任意の `architecture`、値/単位付き `parameters`、制約、PCB制約、未確定条件、データシートURI、設計ルール
- `nets`: 一意の `name`、任意の `kind` (`signal` / `power` / `ground`)、電圧、説明
- `components`: 参照番号、カタログ内のシンボルID、表示値、pin番号からnet名への明示マップ、意図的なno-connect、フットプリント、型番、定格、データシート

対応する回路シンボルIDは `circuitstudio/catalog.py` に明示されています。カタログ外の型番やピン番号は推測せず、回路図出力を止めます。汎用シンボルを使った場合も、実部品のフットプリントや電気定格が特定されたことにはなりません。

単位文字列は、例 `12V`, `5mA`, `1kΩ`, `0.125W` のようなSI接頭辞を使えます。未知単位は計算から除外され、診断は `UNKNOWN` になります。

## 状態

診断の `status` は `PASS`, `FAIL`, `WARNING`, `UNKNOWN`, `NOT_EXECUTED` のいずれかです。構文/スキーマエラーはコンパイル前に別の例外として返します。KiCadへの書き込みは構造解析でFAILがない場合だけ行います。UNKNOWNやWARNINGがあっても、出力は電気的な承認を意味しません。
