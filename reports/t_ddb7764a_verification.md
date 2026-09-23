# verification_evidence — t_ddb7764a

## 実施内容
7日間カメラ差益データ集計スクリプト実装 + 結論レポート出力

## 検証コマンド

$ python3 scripts/camera_7d_aggregate.py
{"Nikon Z8": {"days": 4, "repro_rate": 1.0, "median_mean": -7.8, "median_stdev": 5.6, "consistent": true, "direction": "マイナス", "verdict": "実在の逆アービトラージ機会（Z8一貫安値）", "matched_mean": 7.2, "yahoo_mean": 23}, "Nikon Z9": {"days": 4, "repro_rate": 1.0, "median_mean": 16.9, "median_stdev": 5.9, "consistent": true, "direction": "プラス", "verdict": "実在の仕入れ機会（Z9安定差益）", "matched_mean": 5.8, "yahoo_mean": 10.5}}

$ grep -E '判定|妥当|過大' reports/camera_monitor_7d_conclusion.md
## 機種別判定
| **判定** | 実在の逆アービトラージ機会（Z8一貫安値） | 実在の仕入れ機会（Z9安定差益） |
月額980円は妥当（Z9安定差益検出で年間11760円分の判断材料）

$ wc -l reports/camera_monitor_7d_conclusion.md
33 reports/camera_monitor_7d_conclusion.md

## 検証結果
- 集計スクリプト正常終了（exit 0）
- Z9: 実在の仕入れ機会（再現率1.0、中央値+16.9%安定）
- Z8: 実在の逆アービトラージ機会（再現率1.0、中央値-7.8%一貫）
- 月額980円はZ9安定差益で妥当と判定
