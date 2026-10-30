# CircuitStudio AI — 検証レポート

- プロジェクト: RP2040_12V_HBridge
- 設計意図: RP2040の3.3 V GPIOから12 V DCモーターを正転・逆転・PWM制御する。
- 判定: 電気安全の承認は未実施
- KiCad ERC: NOT_EXECUTED

## 診断

| 状態 | 重大度 | 検査ID | 対象 | 根拠 | 推奨 |
|---|---|---|---|---|---|
| UNKNOWN | warning | DESIGN_ASSUMPTION_UNKNOWN |  | 未確定条件: モーター連続電流 | 値を確認してDSLに反映してください。 |
| UNKNOWN | warning | DESIGN_ASSUMPTION_UNKNOWN |  | 未確定条件: 停止電流 | 値を確認してDSLに反映してください。 |
| UNKNOWN | warning | DESIGN_ASSUMPTION_UNKNOWN |  | 未確定条件: ゲートドライバ型番 | 値を確認してDSLに反映してください。 |
| UNKNOWN | warning | DESIGN_ASSUMPTION_UNKNOWN |  | 未確定条件: MOSFET型番と放熱条件 | 値を確認してDSLに反映してください。 |
| UNKNOWN | warning | DESIGN_ASSUMPTION_UNKNOWN |  | 未確定条件: デッドタイム | 値を確認してDSLに反映してください。 |
| UNKNOWN | warning | DESIGN_ASSUMPTION_UNKNOWN |  | 未確定条件: 保護方式 | 値を確認してDSLに反映してください。 |
| FAIL | error | DSL_EMPTY_CIRCUIT |  | components が空です。出力できる回路要素がありません。 | 部品と接続を指定してください。安全条件の不足だけなら design.unknowns に残し、実体の推定はしないでください。 |
| WARNING | warning | POWER_NET_UNUSED | VM | power net 'VM' に接続部品がありません。 | 電源/GND接続を確認してください。 |
| WARNING | warning | POWER_NET_UNUSED | 3V3 | power net '3V3' に接続部品がありません。 | 電源/GND接続を確認してください。 |
| WARNING | warning | POWER_NET_UNUSED | GND | ground net 'GND' に接続部品がありません。 | 電源/GND接続を確認してください。 |
| UNKNOWN | warning | POWER_GROUND_CONNECTIVITY_UNKNOWN |  | 電源/GNDのいずれかが部品ピンに接続されていません。 | 電源/GNDの端子割当と実際の電流帰路を確認してください。 |
| UNKNOWN | critical | HBRIDGE_OPERATING_DATA |  | 未確定: モーター連続電流, モーター停止電流。電流定格・発熱・ゲート駆動を判断できません。 | モーターの連続/停止電流、最大電源電圧、実際のゲート駆動条件を測定値またはデータシートで指定してください。 |
| FAIL | error | HBRIDGE_SWITCH_COUNT |  | 離散MOSFET構成は4スイッチを想定しますが、検出した個数は0です。 | ブリッジ構成を確認し、各FETの高側/低側と端子割当を明示してください。 |
| UNKNOWN | critical | HBRIDGE_DEAD_TIME |  | デッドタイム条件がありません。上下アーム同時導通の可能性を評価できません。 | ゲートドライバのデータシートとMOSFET切替時間からデッドタイムを設計してください。 |
| UNKNOWN | critical | HBRIDGE_OVERCURRENT |  | 過電流保護が確認できません。停止電流や短絡時の保護を証明できません。 | 電流制限/ヒューズと故障時遮断の設計値を追加してください。 |
| UNKNOWN | critical | HBRIDGE_HIGH_SIDE_DRIVE |  | 高側ゲート駆動方式が確定していません。 | ハイサイドのゲート電圧/デューティ条件に対応するドライバを指定してください。 |
| UNKNOWN | critical | HBRIDGE_TRANSIENT_PROTECTION |  | 誘導性負荷の過渡保護が確認できません。 | 循環電流経路、クランプ素子、過渡電圧定格を検証してください。 |
| UNKNOWN | critical | HBRIDGE_RESET_STATE |  | 起動/リセット時の安全状態が確認できません。 | RP2040起動中の入力状態とゲートの既定オフを回路とファームウェアで確認してください。 |
| WARNING | warning | HBRIDGE_BULK_CAP |  | VM-GND間のバルクコンデンサがネット接続から確認できません。 | モーター電源の配線インダクタンス、電流リップル、部品のリップル電流定格に基づいて配置してください。 |

KiCad ERCは実行していません: 意味解析に失敗したためERCを実行しませんでした。

## 制限

電気診断は明示されたDSL値に対する保守的な検査です。実機、安全動作領域、熱、EMC、製造可能性を保証しません。
