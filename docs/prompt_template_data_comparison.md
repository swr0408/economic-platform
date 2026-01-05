# データ比較機能設定テンプレート

新規指標追加テンプレートの「データ比較機能」セクションとして使用します。

---

================================================================================
【データ比較機能（overlayConfig.ts）】
================================================================================
■ 比較対象として追加: はい / いいえ

■ overlayConfig.ts登録情報:
```typescript
{
  id: '{snake_case}',              // 例: us_cpi_yoy
  name: '{指標名（日本語）}',        // 例: CPI（前年比）
  nameEn: '{指標名（英語）}',        // 例: CPI YoY
  frequency: 'monthly',            // daily / weekly / monthly / quarterly
  country: 'usa',                  // 省略可（デフォルト: usa）
  category: '{category}',          // economy / consumer / employment / prices / policy / market
  subCategory: '{subCategory}',    // gdp / sentiment / retail / cpi / ppi 等
  apiEndpoint: '/api/usa/{category}/dashboard',  // ダッシュボードAPIエンドポイント
  dataKey: '{dataKey}',            // APIレスポンスのキー名
  valueField: '{field}',           // 使用するフィールド（省略可: yoy / mom / value 等）
  chartType: 'line',               // line（デフォルト）/ bar
  unit: '%',                       // % / K / M / B / H 等（省略可）
}
```

■ カテゴリ・サブカテゴリ一覧:
| category | 説明 | subCategory例 |
|----------|------|---------------|
| economy | 経済 | gdp, sentiment, production |
| consumer | 消費 | retail, spending, confidence |
| employment | 雇用 | jobs, claims, wages |
| prices | 物価 | cpi, ppi, pce_deflator |
| policy | 金融政策 | interest_rate, fed |
| market | 市場 | forex_usd, forex_jpy, index_us, bond, commodity_metal |

■ 複数系列を登録する場合（YoY/MoM等）:
```typescript
// 前年比
{ id: '{snake_case}_yoy', valueField: 'yoy', chartType: 'line', ... },
// 前月比
{ id: '{snake_case}_mom', valueField: 'mom', chartType: 'bar', ... },
```

■ 推奨比較指標（関連性の高い指標をコメントで記載）:
- {関連指標1}: {理由}
- {関連指標2}: {理由}
- {関連指標3}: {理由}

■ データ比較ボタン初期選択指標:
チャートから「データ比較」ボタン押下時に初期選択される指標を設定
```typescript
// CPIチャートの例: CPI（前年比）、コアCPI（前年比）、政策金利を初期選択
onClick={() => window.open('/compare?s=us_cpi_yoy&s=us_core_cpi_yoy&s=policy_rate', '_blank')}
```
設定値: s={自身のID}&s={関連指標1}&s={関連指標2}（最大6個まで）

================================================================================

---

## 利用可能な指標一覧（参考）

### 経済（economy）

#### GDP関連
| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| gdp_growth | GDP成長率（前期比年率） | 四半期 | % |
| potential_gdp_real | 実質潜在成長率 | 四半期 | % |
| potential_gdp_nominal | 名目潜在成長率 | 四半期 | % |

#### 金融環境・景況感
| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| bank_lending | 銀行貸し出し態度（SLOOS） | 四半期 | % |
| fci_baseline | FCI-G（Baseline 3年） | 月次 | - |
| fci_oneyear | FCI-G（1年ルックバック） | 月次 | - |
| nfci | シカゴ連銀金融環境指数（NFCI） | 週次 | - |
| ism_manufacturing | ISM製造業景況指数 | 月次 | - |
| ism_non_manufacturing | ISM非製造業景況指数 | 月次 | - |
| philadelphia_fed | フィラデルフィア連銀景況指数 | 月次 | - |
| empire_state | NY連銀製造業景況指数 | 月次 | - |
| nfib_business_optimism | NFIB中小企業楽観指数 | 月次 | - |

#### 生産
| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| industrial_production_yoy | 鉱工業生産（前年比） | 月次 | % |
| capacity_utilization | 設備稼働率 | 月次 | % |
| durable_goods_mom | 耐久財受注（前月比） | 月次 | % |

---

### 雇用（employment）

#### 雇用統計
| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| nonfarm_payrolls | 非農業部門雇用者数 | 月次 | K |
| private_payrolls | 民間雇用者数 | 月次 | K |
| adp_employment | ADP雇用者数 | 月次 | K |
| unemployment_rate | 失業率 | 月次 | % |
| u6_rate | U6失業率 | 月次 | % |
| labor_force_participation | 労働参加率 | 月次 | % |
| employment_population_ratio | 就業率 | 月次 | % |
| jolts_openings | JOLTS求人件数 | 月次 | M |
| jolts_hires | JOLTS採用数 | 月次 | M |
| jolts_quits | JOLTS自発的離職数 | 月次 | M |

#### 失業保険
| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| initial_claims | 新規失業保険申請件数 | 週次 | K |
| continued_claims | 継続失業保険申請件数 | 週次 | K |
| challenger_job_cuts | チャレンジャー人員削減 | 月次 | K |

#### 賃金
| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| average_hourly_earnings_yoy | 平均時給（前年比） | 月次 | % |
| average_hourly_earnings_mom | 平均時給（前月比） | 月次 | % |
| atlanta_fed_wage | アトランタ連銀賃金トラッカー | 月次 | % |
| employment_cost_index | 雇用コスト指数 | 四半期 | % |
| unit_labor_cost | 単位労働コスト | 四半期 | % |
| labor_productivity | 労働生産性 | 四半期 | % |
| indeed_wage_tracker | Indeed賃金トラッカー | 月次 | % |
| overtime_hours | 平均残業時間 | 月次 | H |

---

### 消費（consumer）

#### 小売
| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| retail_sales_mom | 小売売上高（前月比） | 月次 | % |
| retail_sales_yoy | 小売売上高（前年比） | 月次 | % |
| retail_sales_ex_auto_mom | 小売売上高（自動車除く・前月比） | 月次 | % |
| retail_control | コントロールグループ（前月比） | 月次 | % |
| carts | シカゴ連銀小売指数（CARTS） | 週次 | - |
| visa_spending | Visa支出モメンタム指数 | 週次 | % |
| affinity_spending | クレジット/デビットカード支出 | 週次 | % |
| redbook | レッドブック（前年比） | 週次 | % |
| total_vehicle_sales | 自動車販売台数 | 月次 | M |

#### 支出・所得
| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| pce_mom | PCE（前月比） | 月次 | % |
| personal_income_mom | 個人所得（前月比） | 月次 | % |
| personal_income_yoy | 個人所得（前年比） | 月次 | % |
| personal_saving_rate | 個人貯蓄率 | 月次 | % |
| disposable_income | 可処分所得（前年比） | 月次 | % |
| consumer_credit | クレジットカードローン残高（前月比） | 月次 | % |
| delinquency_rate | クレジットカードローン延滞率 | 四半期 | % |

#### 消費者信頼感
| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| cb_consumer_confidence | CB消費者信頼感指数 | 月次 | - |
| cb_jobs_plentiful | CB雇用機会業況判断（仕事豊富） | 月次 | % |
| cb_jobs_hard | CB雇用機会業況判断（仕事困難） | 月次 | % |
| cb_jobs_differential | CB雇用機会業況判断（差分） | 月次 | % |
| michigan_consumer_sentiment | ミシガン大学消費者信頼感指数 | 月次 | - |

---

### 物価（prices）

#### CPI
| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| us_cpi_yoy | CPI（前年比） | 月次 | % |
| us_cpi_mom | CPI（前月比） | 月次 | % |
| us_core_cpi_yoy | コアCPI（前年比） | 月次 | % |
| us_core_cpi_mom | コアCPI（前月比） | 月次 | % |

---

### 金融政策（policy）

| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| policy_rate | 政策金利（FFレート） | 日次 | % |
| term_premium | タームプレミアム（ACM） | 日次 | % |
| expected_rate | 期待短期金利 | 日次 | % |

---

### 市場（market）

#### 為替（ドルストレート）
| ID | 指標名 | 頻度 |
|---|---|---|
| usdjpy | ドル円 | 日次 |
| eurusd | ユーロドル | 日次 |
| gbpusd | ポンドドル | 日次 |
| audusd | 豪ドル米ドル | 日次 |
| nzdusd | NZドル米ドル | 日次 |
| usdcad | ドルカナダ | 日次 |
| usdchf | ドルスイス | 日次 |

#### 為替（クロス円）
| ID | 指標名 | 頻度 |
|---|---|---|
| eurjpy | ユーロ円 | 日次 |
| gbpjpy | ポンド円 | 日次 |
| audjpy | 豪ドル円 | 日次 |
| nzdjpy | NZドル円 | 日次 |
| cadjpy | カナダ円 | 日次 |
| chfjpy | スイス円 | 日次 |

#### 為替（その他クロス）
| ID | 指標名 | 頻度 |
|---|---|---|
| eurgbp | ユーロポンド | 日次 |
| euraud | ユーロ豪ドル | 日次 |
| eurnzd | ユーロNZドル | 日次 |
| eurcad | ユーロカナダ | 日次 |
| eurchf | ユーロスイス | 日次 |
| gbpaud | ポンド豪ドル | 日次 |
| gbpnzd | ポンドNZドル | 日次 |
| gbpcad | ポンドカナダ | 日次 |
| gbpchf | ポンドスイス | 日次 |
| audnzd | 豪ドルNZドル | 日次 |
| audcad | 豪ドルカナダ | 日次 |
| audchf | 豪ドルスイス | 日次 |
| nzdcad | NZドルカナダ | 日次 |
| nzdchf | NZドルスイス | 日次 |
| cadchf | カナダスイス | 日次 |

#### 通貨インデックス
| ID | 指標名 | 頻度 |
|---|---|---|
| dxy | ドルインデックス | 日次 |

#### 米国株価指数
| ID | 指標名 | 頻度 |
|---|---|---|
| sp500 | S&P500 | 日次 |
| dow | ダウ平均 | 日次 |
| nasdaq100 | ナスダック100 | 日次 |
| nasdaq | ナスダック総合 | 日次 |
| russell2000 | ラッセル2000 | 日次 |
| sox | フィラデルフィア半導体指数 | 日次 |
| vix | VIX（恐怖指数） | 日次 |

#### 日本・アジア株価指数
| ID | 指標名 | 頻度 |
|---|---|---|
| nikkei225 | 日経平均 | 日次 |
| topix | TOPIX | 日次 |
| hangseng | ハンセン指数 | 日次 |

#### 欧州株価指数
| ID | 指標名 | 頻度 |
|---|---|---|
| dax | DAX | 日次 |
| ftse100 | FTSE100 | 日次 |
| cac40 | CAC40 | 日次 |

#### 債券利回り
| ID | 指標名 | 頻度 | 単位 |
|---|---|---|---|
| us02y | 米国2年債利回り | 日次 | % |
| us10y | 米国10年債利回り | 日次 | % |
| us30y | 米国30年債利回り | 日次 | % |

#### 貴金属
| ID | 指標名 | 頻度 |
|---|---|---|
| gold | 金（ドル建て） | 日次 |
| silver | 銀（ドル建て） | 日次 |
| copper | 銅 | 日次 |

#### エネルギー
| ID | 指標名 | 頻度 |
|---|---|---|
| crude_oil | 原油（WTI） | 日次 |
| brent_oil | 原油（ブレント） | 日次 |
| natural_gas | 天然ガス | 日次 |

#### 計算値
| ID | 指標名 | 頻度 |
|---|---|---|
| nikkei_usd | 日経平均（ドル建て） | 日次 |
| gold_jpy | 金（円建て） | 日次 |
| gold_eur | 金（ユーロ建て） | 日次 |

---

## プロンプト例

### CPI分析用プロンプト例

```
## 分析対象
CPI（消費者物価指数）

## 利用可能データ
- us_cpi_yoy: CPI（前年比）
- us_cpi_mom: CPI（前月比）
- us_core_cpi_yoy: コアCPI（前年比）
- us_core_cpi_mom: コアCPI（前月比）

## 比較推奨指標
物価関連:
- pce_deflator_yoy: PCEデフレーター（前年比）
- pce_deflator_mom: PCEデフレーター（前月比）

金融政策関連:
- policy_rate: 政策金利（FFレート）
- us02y: 米国2年債利回り
- us10y: 米国10年債利回り

為替:
- usdjpy: ドル円
- dxy: ドルインデックス

## 分析ポイント
1. CPIとコアCPIの乖離
2. 前年比と前月比のトレンド
3. 金融政策への影響（利上げ/利下げ期待）
4. 為替市場への影響
```

### 雇用統計分析用プロンプト例

```
## 分析対象
雇用統計

## 利用可能データ
- nonfarm_payrolls: 非農業部門雇用者数
- unemployment_rate: 失業率
- average_hourly_earnings_yoy: 平均時給（前年比）
- labor_force_participation: 労働参加率

## 比較推奨指標
雇用先行指標:
- initial_claims: 新規失業保険申請件数
- jolts_openings: JOLTS求人件数
- adp_employment: ADP雇用者数

賃金インフレ:
- atlanta_fed_wage: アトランタ連銀賃金トラッカー
- employment_cost_index: 雇用コスト指数

市場:
- usdjpy: ドル円
- us10y: 米国10年債利回り
- sp500: S&P500
```

---

## 頻度の互換性

データ比較時は頻度の異なる指標を組み合わせることができます：
- 日次データは週次・月次・四半期データと比較可能
- 週次データは月次・四半期データと比較可能
- 月次データは四半期データと比較可能

**注意**: 頻度が異なる場合、より粗い頻度に合わせてデータポイントが調整されます。
