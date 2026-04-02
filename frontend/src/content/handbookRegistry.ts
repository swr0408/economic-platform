/**
 * データハンドブック - コンテンツレジストリ
 *
 * indicatorId は countryData.tsx の indicator.code に対応。
 * country/category を付与することで辞書ページでのフィルタリングに使う。
 */

export interface HandbookEntry {
  /** countryData.tsx の indicator.code と一致 */
  indicatorId: string
  /** 表示タイトル */
  title: string
  /** 国コード (usa, japan, eurozone, ...) */
  country: string
  /** カテゴリコード (policy, economy, consumer, employment, inflation, housing) */
  category: string
  /** 1行の概要 */
  summary: string
  /** マークダウン本文を返す動的インポート */
  loadContent: () => Promise<string>
  /** 関連指標ID */
  relatedIndicators?: string[]
  /** タグ（検索用） */
  tags?: string[]
}

// --- マークダウンファイルの動的インポートヘルパー ---
// Vite の import.meta.glob を使い、ビルド時にすべてのmdファイルを列挙
const mdModules = import.meta.glob<string>('./indicators/**/*.md', {
  query: '?raw',
  import: 'default',
})

function loadMd(path: string): () => Promise<string> {
  const key = `./indicators/${path}`
  const loader = mdModules[key]
  if (!loader) {
    return () => Promise.resolve(`> コンテンツ準備中: ${path}`)
  }
  return loader as () => Promise<string>
}

// ====================================================================
// レジストリ
// ====================================================================

export const HANDBOOK_ENTRIES: HandbookEntry[] = [
  // --- USA / 概要 ---
  {
    indicatorId: 'usa-overview',
    title: 'アメリカ経済の概要',
    country: 'usa',
    category: 'economy',
    summary: '個人消費主導の内需型経済。PCEがGDPの約68%を占め、景気判断は雇用・賃金・消費・住宅・金融環境が中心。FRB・米国債・貿易構造の基本も整理。',
    loadContent: loadMd('usa/usa-overview.md'),
    relatedIndicators: ['gdp-growth', 'policy-rate', 'pce', 'nonfarm-payrolls'],
    tags: ['アメリカ', '経済構造', 'PCE', 'FRB', 'FOMC', '米国債', '貿易', '内需', '政治', '大統領選挙'],
  },

  // --- USA / 金融政策 ---
  {
    indicatorId: 'policy-rate',
    title: '政策金利（FF金利）',
    country: 'usa',
    category: 'policy',
    summary: 'FRBが設定する短期金利の誘導目標。金融市場全体の金利水準に影響する最重要指標。',
    loadContent: loadMd('usa/policy-rate.md'),
    relatedIndicators: ['fed-watch', 'sofr-volatility'],
    tags: ['FRB', 'FOMC', '金利', 'Federal Funds Rate'],
  },
  {
    indicatorId: 'fed-watch',
    title: 'Fed Watch',
    country: 'usa',
    category: 'policy',
    summary: 'CME FedWatch Toolに基づくFOMC会合ごとの利上げ・利下げ確率。',
    loadContent: loadMd('usa/fed-watch.md'),
    relatedIndicators: ['policy-rate'],
    tags: ['FRB', 'FOMC', 'CME', '金利先物'],
  },
  {
    indicatorId: 'oas',
    title: 'OAS（社債・信用スプレッド）',
    country: 'usa',
    category: 'policy',
    summary: '社債スプレッド（OAS）は企業の資金調達環境と信用不安を映す指標。IG/HY/BBBの各スプレッドからリスク許容度を確認する。',
    loadContent: loadMd('usa/oas.md'),
    relatedIndicators: ['cmdi', 'financial-stress-index', 'policy-rate'],
    tags: ['OAS', '社債', 'スプレッド', '信用', 'クレジット', 'IG', 'HY', 'BBB', 'ハイイールド', '投資適格', 'HYG', 'EBP', 'FRED'],
  },
  {
    indicatorId: 'term-premium',
    title: 'タームプレミアム',
    country: 'usa',
    category: 'policy',
    summary: 'NY Fedが推計する長期債保有の追加リスク補償。長期金利上昇が景気期待か需給・財政要因かを切り分け、雇用環境との整合性も確認できる。',
    loadContent: loadMd('usa/term-premium.md'),
    relatedIndicators: ['us-interest-rate-spread', 'us-treasury-yields', 'policy-rate', 'unemployment', 'initial-claims'],
    tags: ['タームプレミアム', 'NY Fed', '長期金利', '実質金利', 'QT', '国債', '需給', '財政', '失業率', '失業保険'],
  },

  // --- USA / 期待政策金利 ---
  {
    indicatorId: 'expected-policy-rate',
    title: '期待政策金利',
    country: 'usa',
    category: 'policy',
    summary: '市場が織り込む先行きの政策金利パス。GDPギャップとインフレ見通しを組み合わせ、中央銀行の反応関数に対する市場の解釈として読む。',
    loadContent: loadMd('usa/expected-policy-rate.md'),
    relatedIndicators: ['term-premium', 'policy-rate', 'neutral-rate', 'potential-growth', 'gdp-growth'],
    tags: ['期待政策金利', 'OIS', '短期金利先物', 'GDPギャップ', '反応関数', '中立金利', '自然利子率', 'テイラールール'],
  },

  // --- USA / 経済 ---
  {
    indicatorId: 'gdp-growth',
    title: 'GDP成長率',
    country: 'usa',
    category: 'economy',
    summary: '米国の国内総生産の四半期成長率（前期比年率）。景気の全体像を示す最も包括的な指標。',
    loadContent: loadMd('usa/gdp-growth.md'),
    relatedIndicators: ['gdpnow', 'gdp-components-growth', 'gdp-contributions'],
    tags: ['GDP', 'BEA', '景気'],
  },
  {
    indicatorId: 'ism-manufacturing',
    title: 'ISM製造業景況指数',
    country: 'usa',
    category: 'economy',
    summary: '5つの拡散指数を等ウェイト合成した製造業景況指標。50は製造業分岐点、47.5は全体経済の目安。前年差ベースでS&P500前年比と強い関係を示す。',
    loadContent: loadMd('usa/ism-manufacturing.md'),
    relatedIndicators: ['taiwan-export-orders', 'cn-electronics-stock', 'caixin-pmi', 'ism-components', 'order-inventory-balance', 'sp-pmi-chart', 'cot-crude-oil', 'global-manufacturing-pmi', 'sp500-valuation'],
    tags: ['ISM', 'PMI', '製造業', '景気先行指標', '50', '47.5', 'S&P500', '前年差', '景気循環', '台湾輸出受注', 'SOX', '中国財新PMI'],
  },
  {
    indicatorId: 'ism-components',
    title: 'ISM製造業サブインデックス',
    country: 'usa',
    category: 'economy',
    summary: '新規受注は先行サブ指数として最も重視される。需要の改善は将来の生産・活動の持ち直しにつながりやすく、40割れは景気後退局面で見られる警戒水準。',
    loadContent: loadMd('usa/ism-components.md'),
    relatedIndicators: ['ism-manufacturing', 'order-inventory-balance', 'durable-goods'],
    tags: ['ISM', '新規受注', 'New Orders', 'サブインデックス', '先行指標', '製造業', '景気後退'],
  },
  {
    indicatorId: 'order-inventory-balance',
    title: 'ISM製造業受注在庫バランス',
    country: 'usa',
    category: 'economy',
    summary: 'ISM新規受注−在庫の差。1〜3か月先の生産活動を読む先行指標で、3MA底入れで在庫循環の改善を捉えやすい。日経平均の景気循環補助指標としても有用。',
    loadContent: loadMd('usa/order-inventory-balance.md'),
    relatedIndicators: ['ism-manufacturing', 'ism-components', 'nikkei-225', 'global-manufacturing-pmi', 'cn-electronics-stock'],
    tags: ['ISM', '受注在庫バランス', 'New Orders', 'Inventories', '在庫循環', '生産', '先行指標', '日経平均', '製造業'],
  },
  {
    indicatorId: 'ism-non-manufacturing',
    title: 'ISM非製造業景況指数（ISM Services PMI）',
    country: 'usa',
    category: 'economy',
    summary: '米国GDP73%を占めるサービス部門の景況感。50はサービス部門の分岐点、48.1はGDP全体の目安。Supplier Deliveriesの逆符号解釈やPrices指数のインフレ示唆を含む。',
    loadContent: loadMd('usa/ism-non-manufacturing.md'),
    relatedIndicators: ['ism-non-manufacturing-components', 'sp-pmi-chart', 'ism-manufacturing'],
    tags: ['ISM', 'PMI', 'サービス業', '非製造業', 'Services', '50', '48.1', 'GDP', 'New Orders', 'Prices', 'スーパーコア'],
  },

  {
    indicatorId: 'sp-pmi-chart',
    title: 'S&P Global PMI（米国）',
    country: 'usa',
    category: 'economy',
    summary: 'S&P Globalの製造業・サービス業・コンポジットPMI。GDPの方向感にはサービスPMIが有効で、財価格圧力には製造業の投入・産出価格指数を確認する。',
    loadContent: loadMd('usa/sp-pmi.md'),
    relatedIndicators: ['ism-manufacturing', 'ism-non-manufacturing', 'global-manufacturing-pmi'],
    tags: ['PMI', 'S&P Global', '製造業', 'サービス業', '景気', '投入価格', '産出価格'],
  },

  {
    indicatorId: 'durable-goods',
    title: '耐久財受注',
    country: 'usa',
    category: 'economy',
    summary: 'Census BureauのM3調査に基づく製造業の新規受注額。コア資本財受注（非国防・除く航空機）が設備投資の先行指標として最も重要。',
    loadContent: loadMd('usa/durable-goods.md'),
    relatedIndicators: ['ism-manufacturing', 'gdp-growth', 'sp-pmi-chart'],
    tags: ['耐久財受注', 'Durable Goods', 'Core Capital Goods', 'Census Bureau', '設備投資', '製造業', '非国防資本財'],
  },

  // --- USA / 雇用 ---
  {
    indicatorId: 'nonfarm-payrolls',
    title: '非農業部門雇用者数（NFP）',
    country: 'usa',
    category: 'employment',
    summary: '毎月第一金曜発表。事業所調査（CES）のジョブ数と家計調査（CPS）の就業者数の違い・乖離から雇用の質を読む。',
    loadContent: loadMd('usa/nonfarm-payrolls.md'),
    relatedIndicators: ['unemployment', 'adp-employment', 'initial-claims', 'fullpart-time', 'multiple-jobs-parttime'],
    tags: ['NFP', '雇用統計', 'BLS', '労働市場', 'PAYEMS', 'CE16OV', '事業所調査', '家計調査', 'CES', 'CPS'],
  },
  {
    indicatorId: 'adp-employment',
    title: 'ADP雇用統計',
    country: 'usa',
    category: 'employment',
    summary: 'ADP給与台帳データに基づく民間雇用の月次指標。2600万人超のデータから民間労働市場の動向を独自に捉える。',
    loadContent: loadMd('usa/adp-employment.md'),
    relatedIndicators: ['nonfarm-payrolls', 'adp-wage-growth', 'initial-claims'],
    tags: ['ADP', '雇用統計', '民間雇用', '労働市場', 'payroll'],
  },
  {
    indicatorId: 'adp-wage-growth',
    title: 'ADP賃金上昇率中央値',
    country: 'usa',
    category: 'employment',
    summary: 'ADP Pay Insightsによる賃金指標。転職者と継続就業者の賃金上昇率を分けて示し、労働市場の逼迫度や転職プレミアムを把握する。',
    loadContent: loadMd('usa/adp-wage-growth.md'),
    relatedIndicators: ['adp-employment', 'average-hourly-earnings', 'eci'],
    tags: ['ADP', '賃金', 'Pay Insights', '転職者', '継続就業者', '賃金上昇率'],
  },
  {
    indicatorId: 'atlanta-fed-wage',
    title: 'アトランタ連銀賃金トラッカー',
    country: 'usa',
    category: 'employment',
    summary: 'CPS個票から同一個人の賃金変化を追跡。構成変化の影響を排除し、基調的な賃金上昇率を中央値で示す。',
    loadContent: loadMd('usa/atlanta-fed-wage.md'),
    relatedIndicators: ['average-hourly-earnings', 'adp-wage-growth', 'eci'],
    tags: ['アトランタ連銀', '賃金トラッカー', 'Wage Growth Tracker', 'CPS', '賃金', '中央値'],
  },
  {
    indicatorId: 'cb-jobs-labor',
    title: 'CB雇用機会業況判断',
    country: 'usa',
    category: 'employment',
    summary: 'CB消費者信頼感調査の「仕事は豊富」と「仕事を見つけにくい」の差分。家計の体感を通じて失業率の方向感を映す。',
    loadContent: loadMd('usa/cb-jobs-labor.md'),
    relatedIndicators: ['unemployment', 'cb-consumer-confidence', 'jolts-indeed', 'initial-claims'],
    tags: ['CB', '消費者信頼感', '雇用判断', 'labor differential', '失業率', 'Conference Board'],
  },
  {
    indicatorId: 'job-openings-per-unemployed',
    title: '求人倍率（求人数÷失業者）',
    country: 'usa',
    category: 'employment',
    summary: 'JOLTS求人件数÷失業者数で算出。労働市場の需給バランスを直接反映し、賃金・インフレ圧力の先行指標として有効。',
    loadContent: loadMd('usa/job-openings-per-unemployed.md'),
    relatedIndicators: ['nonfarm-payrolls', 'unemployment', 'initial-claims'],
    tags: ['求人倍率', 'JOLTS', '求人', '失業', '労働需給', '賃金', 'BLS'],
  },
  {
    indicatorId: 'jolts-indeed',
    title: 'Indeed求人数とJOLTS求人',
    country: 'usa',
    category: 'employment',
    summary: 'Indeed求人指数でJOLTS求人の方向感を先行把握する。日次の高頻度データと月末ストック統計の関係を整理。',
    loadContent: loadMd('usa/jolts-indeed.md'),
    relatedIndicators: ['job-openings-per-unemployed', 'nonfarm-payrolls', 'initial-claims'],
    tags: ['Indeed', 'JOLTS', '求人', '求人広告', '労働需要', '高頻度', 'BLS'],
  },
  {
    indicatorId: 'unemployment',
    title: '失業率・失業理由別内訳・U-6・採用率・離職率・レイオフ率',
    country: 'usa',
    category: 'employment',
    summary: '失業率の水準だけでなく、理由別内訳（一時解雇・恒久的失職・自発的離職・再参入・新規参入）から景気悪化の質を判断する。',
    loadContent: loadMd('usa/unemployment.md'),
    relatedIndicators: ['nonfarm-payrolls', 'sahm-rule', 'labor-force-participation', 'initial-claims', 'jolts-indeed', 'fullpart-time'],
    tags: ['失業率', 'U-6', '失業内訳', '一時解雇', '恒久的失職', '自発的離職', '再参入者', '採用率', '離職率', 'レイオフ', 'BLS', 'CPS', 'JOLTS'],
  },
  {
    indicatorId: 'sahm-rule',
    title: 'サームルール',
    country: 'usa',
    category: 'employment',
    summary: '失業率3か月移動平均の直近底からの上昇幅で景気後退入りを判定する補助指標。0.50pt超で警戒シグナル。',
    loadContent: loadMd('usa/sahm-rule.md'),
    relatedIndicators: ['unemployment', 'nonfarm-payrolls', 'initial-claims'],
    tags: ['サームルール', 'Sahm Rule', '景気後退', 'リセッション', '失業率'],
  },
  {
    indicatorId: 'labor-force-participation',
    title: '労働参加率',
    country: 'usa',
    category: 'employment',
    summary: '労働力人口÷生産年齢人口。失業率では見えない労働供給面の構造変化を把握するのに重要。',
    loadContent: loadMd('usa/labor-force-participation.md'),
    relatedIndicators: ['unemployment', 'nonfarm-payrolls', 'fullpart-time'],
    tags: ['労働参加率', 'LFPR', '労働供給', 'プライムエイジ', 'BLS'],
  },
  {
    indicatorId: 'fullpart-time',
    title: 'フルタイム・パートタイム就業',
    country: 'usa',
    category: 'employment',
    summary: 'フルタイム/パートタイム就業の構成から雇用の質を判断。パートタイム比率の上昇は平均賃金の下押し圧力となりやすい。',
    loadContent: loadMd('usa/fullpart-time.md'),
    relatedIndicators: ['nonfarm-payrolls', 'unemployment', 'labor-force-participation', 'average-hourly-earnings', 'atlanta-fed-wage', 'employment-cost-index'],
    tags: ['フルタイム', 'パートタイム', '雇用の質', '不本意パート', 'パートタイム比率', '賃金', 'BLS'],
  },
  {
    indicatorId: 'multiple-jobs-parttime',
    title: '複数の仕事を持つ労働者（Multiple Jobholders）',
    country: 'usa',
    category: 'employment',
    summary: '2つ以上の仕事を持つ就業者の動向。家計の収入補完ニーズ、労働需要の強さ、働き方の構造変化を間接的に映す補助指標。',
    loadContent: loadMd('usa/multiple-jobs-parttime.md'),
    relatedIndicators: ['fullpart-time', 'average-hourly-earnings', 'average-weekly-working-hours', 'nonfarm-payrolls'],
    tags: ['Multiple Jobholders', '複数就業', '副業', 'ギグワーク', '兼業', 'BLS', 'CPS', '雇用の質'],
  },
  {
    indicatorId: 'average-hourly-earnings',
    title: '平均時給',
    country: 'usa',
    category: 'employment',
    summary: '賃金インフレ圧力の代表指標。サービス業の人件費を通じてインフレに波及しやすく、金融政策判断にも直結する。',
    loadContent: loadMd('usa/average-hourly-earnings.md'),
    relatedIndicators: ['nonfarm-payrolls', 'job-openings-per-unemployed', 'average-weekly-working-hours'],
    tags: ['平均時給', '賃金', 'AHE', '賃金インフレ', 'BLS'],
  },
  {
    indicatorId: 'average-weekly-working-hours',
    title: '平均週労働時間',
    country: 'usa',
    category: 'employment',
    summary: '雇用者数より先に景気変化を映す先行指標。企業は人員削減の前にまず労働時間を調整するため、景気転換点の早期把握に有効。',
    loadContent: loadMd('usa/average-weekly-working-hours.md'),
    relatedIndicators: ['nonfarm-payrolls', 'average-hourly-earnings', 'unemployment'],
    tags: ['週労働時間', 'AWHAETP', 'AWHMAN', 'AWHNONAG', 'LEI', '景気先行指標', 'BLS'],
  },
  {
    indicatorId: 'initial-claims',
    title: '新規失業保険申請件数',
    country: 'usa',
    category: 'employment',
    summary: 'レイオフや雇用悪化の初期変化を週次で捉える高頻度指標。雇用統計の前哨戦として重要。',
    loadContent: loadMd('usa/initial-claims.md'),
    relatedIndicators: ['nonfarm-payrolls', 'unemployment', 'sahm-rule'],
    tags: ['失業保険', '新規申請', 'Initial Claims', 'レイオフ', 'DOL'],
  },
  {
    indicatorId: 'challenger-job-cuts',
    title: 'チャレンジャー人員削減',
    country: 'usa',
    category: 'employment',
    summary: '企業の人員削減計画を集計した指標。雇用悪化や企業マインドの変化を早めに把握する補助材料。',
    loadContent: loadMd('usa/challenger-job-cuts.md'),
    relatedIndicators: ['initial-claims', 'unemployment', 'nonfarm-payrolls'],
    tags: ['チャレンジャー', 'Challenger', '人員削減', 'Job Cuts', 'レイオフ', '解雇'],
  },
  {
    indicatorId: 'overtime-hours',
    title: '平均残業時間（製造業）',
    country: 'usa',
    category: 'employment',
    summary: '製造業の残業時間は雇用に先行しやすい景気先行指標。企業は採用前にまず労働時間を調整するため、雇用拡大の予兆を把握できる。',
    loadContent: loadMd('usa/overtime-hours.md'),
    relatedIndicators: ['average-weekly-working-hours', 'nonfarm-payrolls', 'fullpart-time', 'initial-claims'],
    tags: ['残業時間', 'Overtime', '製造業', 'LEI', '景気先行指標', '労働時間', 'BLS'],
  },
  {
    indicatorId: 'temporary-help-services',
    title: '臨時社員（Temporary Help Services）',
    country: 'usa',
    category: 'employment',
    summary: '派遣・臨時スタッフの雇用者数。企業が正社員より先に調整しやすい雇用であり、総雇用や景気の転換点を早期に察知する先行指標。',
    loadContent: loadMd('usa/temporary-help-services.md'),
    relatedIndicators: ['nonfarm-payrolls', 'initial-claims', 'jolts-indeed', 'average-weekly-working-hours', 'unemployment'],
    tags: ['臨時社員', 'Temporary Help', '派遣', 'TEMPHELPS', '先行指標', 'BLS', 'CES', 'Employment Trends Index'],
  },
  {
    indicatorId: 'unit-labor-cost',
    title: '単位労働コスト（ULC）',
    country: 'usa',
    category: 'employment',
    summary: '1単位の産出あたり労働コスト。報酬と生産性のバランスから賃金インフレ圧力・企業収益圧迫・景気の質を判断する指標。',
    loadContent: loadMd('usa/unit-labor-cost.md'),
    relatedIndicators: ['average-hourly-earnings', 'nonfarm-payrolls', 'cpi', 'pce-deflator'],
    tags: ['単位労働コスト', 'ULC', 'Unit Labor Cost', '労働生産性', '賃金', 'インフレ', 'BLS', '企業収益'],
  },

  {
    indicatorId: 'pce-food-recreation',
    title: 'PCEデフレーター飲食宿泊・娯楽 / 平均時給',
    country: 'usa',
    category: 'employment',
    summary: '平均時給と飲食・娯楽サービス価格の連動性。サービス業の人件費比重が高いため賃金→価格転嫁が起きやすく、労働需給の逼迫度で関係の強弱が変わる。',
    loadContent: loadMd('usa/pce-food-recreation.md'),
    relatedIndicators: ['average-hourly-earnings', 'cpi', 'cpi-categories', 'pce-deflator'],
    tags: ['賃金', '平均時給', 'サービス価格', '飲食', '娯楽', 'PCEデフレーター', '価格転嫁', '労働需給'],
  },

  // --- USA / 物価 ---
  {
    indicatorId: 'cpi',
    title: 'CPI（消費者物価指数）',
    country: 'usa',
    category: 'inflation',
    summary: '都市部消費者の財・サービス価格変化を測る代表的物価指数。コアCPI、住居費のウエイトと粘着性、エネルギー価格との関係、PCEとの構造差を含む。',
    loadContent: loadMd('usa/cpi.md'),
    relatedIndicators: ['pce-deflator', 'ppi', 'median-cpi', 'housing-indicators', 'zillow-rent-index'],
    tags: ['CPI', 'インフレ', 'BLS', '物価', 'コアCPI', '住居費', 'Shelter', 'エネルギー', 'PCE', '前年比', '消費者物価指数'],
  },

  {
    indicatorId: 'cpi-categories',
    title: 'CPI 項目別',
    country: 'usa',
    category: 'inflation',
    summary: '食品・ガソリンの家計負担と体感物価、ヘッドラインCPIと基調インフレ（コアPCE）の使い分け、低所得層への影響。',
    loadContent: loadMd('usa/cpi-categories.md'),
    relatedIndicators: ['cpi', 'pce-deflator', 'ppi', 'median-cpi'],
    tags: ['CPI', '食品', 'ガソリン', 'エネルギー', '家計負担', 'ヘッドライン', 'コアPCE', '期待インフレ', '低所得層', 'BLS'],
  },

  {
    indicatorId: 'pce-deflator',
    title: 'PCEデフレーター',
    country: 'usa',
    category: 'inflation',
    summary: 'FRBが最も重視するインフレ指標。家計自己負担だけでなく雇用主・政府経由の支出も含み、CPIより広い消費関連物価を捉える。',
    loadContent: loadMd('usa/pce-deflator.md'),
    relatedIndicators: ['cpi', 'ppi', 'median-cpi', 'trimmed-mean-pce'],
    tags: ['PCE', 'デフレーター', 'コアPCE', 'BEA', 'インフレ', '年率', 'FRB', '個人消費支出価格指数'],
  },

  {
    indicatorId: 'gscpi',
    title: 'グローバルサプライチェーン圧力指数（GSCPI）',
    country: 'usa',
    category: 'inflation',
    summary: 'NY Fed公表のサプライチェーン圧力指数。コア財価格に3〜5か月先行しやすく、供給制約の変化から将来の財インフレを読む手掛かり。',
    loadContent: loadMd('usa/gscpi.md'),
    relatedIndicators: ['cpi', 'cpi-categories', 'ppi'],
    tags: ['GSCPI', 'サプライチェーン', 'コア財', '先行指標', 'NY Fed', '供給制約', '物流'],
  },

  {
    indicatorId: 'housing-indicators',
    title: 'CPI住居関連 / Zillow住宅価値指数 / ケースシラー住宅価格指数 / 家賃CPI',
    country: 'usa',
    category: 'inflation',
    summary: 'ShelterはCPIの約36%。OER（約74%）と家賃CPI（約22%）の構造、BLS調査の遅行特性、住宅価格指標との先行・遅行関係を含む住居費インフレの総合解説。',
    loadContent: loadMd('usa/housing-indicators.md'),
    relatedIndicators: ['cpi', 'zillow-rent-cpi', 'cpi-categories', 'existing-home-sales', 'redfin-case-shiller'],
    tags: ['Zillow', 'ZHVI', '住宅価値', 'ケースシラー', 'Case-Shiller', '家賃CPI', '住居費', 'Shelter', 'OER', '帰属家賃', 'BLS', '先行指標'],
  },

  {
    indicatorId: 'zillow-rent-cpi',
    title: 'Zillow家賃指数 / 家賃CPI',
    country: 'usa',
    category: 'inflation',
    summary: 'Zillow家賃指数は家賃CPIに12〜13か月先行しやすい。民間賃料のピークアウト・底打ちから将来の住居費インフレを読む指標。',
    loadContent: loadMd('usa/zillow-rent-cpi.md'),
    relatedIndicators: ['housing-indicators', 'cpi', 'cpi-categories'],
    tags: ['Zillow', 'ZORI', '家賃指数', '家賃CPI', '住居費', 'Shelter', '先行指標', '賃貸市場'],
  },

  {
    indicatorId: 'ppi',
    title: 'PPI（生産者物価指数）',
    country: 'usa',
    category: 'inflation',
    summary: 'BLSが公表する生産者販売価格の体系。財＋サービス＋建設を含む広範なカバレッジで、CPIの約1ヶ月先行指標として機能。',
    loadContent: loadMd('usa/ppi.md'),
    relatedIndicators: ['cpi', 'pce-deflator', 'ism-manufacturing'],
    tags: ['PPI', '生産者物価', 'BLS', 'インフレ', 'FD-ID', 'サービス'],
  },

  {
    indicatorId: 'truflation-us-cpi',
    title: 'Truflation US CPI Inflation Index',
    country: 'usa',
    category: 'inflation',
    summary: '30超のデータソースと1,500万超の価格データを用いた日次更新のリアルタイム型インフレ指標。公式CPI・PCEの補完として方向感や転換点の早期把握に有用。',
    loadContent: loadMd('usa/truflation-us-cpi.md'),
    relatedIndicators: ['cpi', 'pce-deflator', 'cpi-categories'],
    tags: ['Truflation', 'インフレ', 'リアルタイム', '日次', 'CPI', 'PCE', '補完指標', '高頻度'],
  },

  // --- Japan / 金融政策 ---
  {
    indicatorId: 'boj-policy-rate-chart',
    title: '日銀政策金利',
    country: 'japan',
    category: 'policy',
    summary: '日本銀行が設定する無担保コールレート（翌日物）の誘導目標。',
    loadContent: loadMd('japan/boj-policy-rate.md'),
    relatedIndicators: ['boj-meeting-expectations', 'ois-curve-chart'],
    tags: ['日銀', 'BOJ', '金利', 'YCC'],
  },

  // --- Japan / 経済 ---
  {
    indicatorId: 'quarterly-gdp',
    title: 'GDP成長率（日本）',
    country: 'japan',
    category: 'economy',
    summary: '内閣府が四半期ごとに発表する国内総生産の成長率。GDPは付加価値ベースの統計であり、個人消費は居住者家計ベースで整理される。小売販売額やインバウンド消費との統計概念の違いに注意が必要。',
    loadContent: loadMd('japan/gdp-growth.md'),
    relatedIndicators: ['gdp-components', 'gdp-deflator', 'retail-sales'],
    tags: ['GDP', '内閣府', '景気', '個人消費', '付加価値', '帰属家賃', 'インバウンド', '小売販売'],
  },

  {
    indicatorId: 'gdp-deflator',
    title: 'GDPデフレーター',
    country: 'japan',
    category: 'economy',
    summary: '名目GDPを実質GDPで割ったインプリシットな物価指標。交易条件の影響を直接受け、国内付加価値の価格動向を把握する。',
    loadContent: loadMd('japan/gdp-deflator.md'),
    relatedIndicators: ['quarterly-gdp', 'national-cpi', 'cgpi'],
    tags: ['GDPデフレーター', '物価', '内閣府', '交易条件', '付加価値', '四半期'],
  },

  // --- Japan / 物価 ---
  {
    indicatorId: 'national-cpi',
    title: '全国CPI（日本）',
    country: 'japan',
    category: 'inflation',
    summary: '総務省が発表する全国消費者物価指数。生鮮食品を除くコアCPIが日銀の物価目標の対象。',
    loadContent: loadMd('japan/national-cpi.md'),
    relatedIndicators: ['tokyo-cpi', 'sppi', 'cgpi'],
    tags: ['CPI', '物価', '総務省', 'インフレ'],
  },

  {
    indicatorId: 'cgpi',
    title: '企業物価指数（CGPI）',
    country: 'japan',
    category: 'inflation',
    summary: '日本銀行が発表する企業間取引財の物価指数。米国PPIの財部分に相当し、CPI に約7ヶ月先行する。',
    loadContent: loadMd('japan/cgpi.md'),
    relatedIndicators: ['national-cpi', 'sppi', 'ppi'],
    tags: ['CGPI', '企業物価', '日本銀行', '物価', 'インフレ'],
  },

  // --- Japan / 経済（PMI） ---
  {
    indicatorId: 'pmi',
    title: 'S&P Global PMI（日本）',
    country: 'japan',
    category: 'economy',
    summary: 'auじぶん銀行PMI。GDP全体にはサービスPMIが相対的に有効で、財価格・仕入れコストには製造業の投入・産出価格指数を確認する。',
    loadContent: loadMd('japan/pmi.md'),
    relatedIndicators: ['quarterly-gdp', 'cgpi', 'global-manufacturing-pmi'],
    tags: ['PMI', 'S&P Global', 'auじぶん銀行', '製造業', 'サービス業', '景気', '投入価格', '産出価格'],
  },

  // --- Japan / 雇用 ---
  {
    indicatorId: 'shuntou',
    title: '春闘賃上げ率',
    country: 'japan',
    category: 'employment',
    summary: '連合の要求集計結果は春闘賃上げ率の先行材料。要求水準だけでなく中小企業への波及が重要。連合集計と厚労省集計は対象が異なるため数字に差がある。',
    loadContent: loadMd('japan/shuntou.md'),
    relatedIndicators: ['boj-policy-rate-chart', 'national-cpi', 'japan-fundamentals-yen'],
    tags: ['春闘', '賃上げ', '連合', 'Rengo', '要求集計', '中小企業', '賃金', '物価循環', 'BOJ', '厚生労働省'],
  },

  // --- グローバル / 経済 ---
  {
    indicatorId: 'global-manufacturing-pmi',
    title: 'グローバル製造業PMI',
    country: 'global',
    category: 'economy',
    summary: '世界の製造業景況感。原油の景気要因を確認する同時確認指標として有用。',
    loadContent: loadMd('global/global-manufacturing-pmi.md'),
    relatedIndicators: ['ism-manufacturing', 'cot-crude-oil'],
    tags: ['PMI', '製造業', 'グローバル', 'S&P Global', '景況感', '原油'],
  },

  // --- マーケット / 株式 ---
  {
    indicatorId: 'nikkei-225',
    title: '日経平均株価',
    country: 'market',
    category: 'equities',
    summary: '225銘柄の株価平均型指数。半導体・大型値がさ株の影響が大きく、構成・ウエート・補助指標を解説。',
    loadContent: loadMd('market/nikkei-225.md'),
    relatedIndicators: ['topix', 'cftc-positioning', 'anomaly-guide'],
    tags: ['日経平均', 'Nikkei', '株価指数', '半導体', 'アドバンテスト', 'ファーストリテイリング', '東京エレクトロン'],
  },
  {
    indicatorId: 'jpx-investor-trading',
    title: '投資部門別売買状況',
    country: 'market',
    category: 'equities',
    summary: 'JPXの投資部門別売買状況。海外投資家・個人・信託銀行・事業法人など各主体の特徴と読み方。',
    loadContent: loadMd('market/jpx-investor-trading.md'),
    relatedIndicators: ['nikkei-225', 'topix', 'cftc-positioning'],
    tags: ['JPX', '投資部門別', '海外投資家', '個人', '信託銀行', '事業法人', '需給', '自社株買い'],
  },
  {
    indicatorId: 'topix',
    title: 'TOPIX',
    country: 'market',
    category: 'equities',
    summary: '浮動株調整後時価総額加重方式の日本株ベンチマーク。日経平均との相対比較や日銀短観との関係を解説。',
    loadContent: loadMd('market/topix.md'),
    relatedIndicators: ['nikkei-225', 'jpx-investor-trading', 'jpx-pcr'],
    tags: ['TOPIX', '東証', '時価総額加重', '日銀短観', 'ベンチマーク', '地合い'],
  },
  {
    indicatorId: 'jpx-pcr',
    title: '日本株指数 Put/Call Ratio',
    country: 'market',
    category: 'equities',
    summary: '日経225・日経225ミニ・TOPIXオプションのPCR。建玉PCRと取引高PCRの読み方、日経平均VIとの併用を解説。',
    loadContent: loadMd('market/jpx-pcr.md'),
    relatedIndicators: ['nikkei-225', 'topix', 'options-guide'],
    tags: ['PCR', 'Put/Call Ratio', 'オプション', '建玉', '取引高', 'JPX', '日経平均VI', '海外投資家'],
  },

  // --- マーケット / Russell 2000 / Russell 1000 ---
  {
    indicatorId: 'russell2000-russell1000',
    title: 'Russell 2000 / Russell 1000 レシオ',
    country: 'market',
    category: 'equities',
    summary: '小型株 / 大型株の相対レシオ。上昇の質や市場の広がりを見る補助指標。景気・信用環境の変化が表れやすい。',
    loadContent: loadMd('market/russell2000-russell1000.md'),
    relatedIndicators: ['sector-ratio', 'growth-value-ratio', 'cftc-positioning'],
    tags: ['Russell', 'ラッセル', '小型株', '大型株', 'レシオ', 'リスク選好', '景気'],
  },

  // --- マーケット / 金融ストレス指数 ---
  {
    indicatorId: 'financial-stress-index',
    title: '金融ストレス指数（STLFSI4）',
    country: 'market',
    category: 'equities',
    summary: 'セントルイス連銀が算出する金融市場のストレス度合い。0が歴史的平均、正値がストレス増大を示す週次指標。',
    loadContent: loadMd('market/financial-stress-index.md'),
    relatedIndicators: ['russell2000-russell1000', 'sector-ratio', 'gex-dix'],
    tags: ['STLFSI4', '金融ストレス', 'ストレス指数', 'FRED', 'セントルイス連銀', 'リスク'],
  },

  // --- マーケット / 社債市場ディストレス指数（CMDI） ---
  {
    indicatorId: 'cmdi',
    title: '社債市場ディストレス指数（CMDI）',
    country: 'market',
    category: 'equities',
    summary: 'NY Fedが算出する社債市場の機能不全度を0-1スケールで示す指数。一次・二次市場の情報を統合し、企業の資金調達環境を捉える。',
    loadContent: loadMd('market/cmdi.md'),
    relatedIndicators: ['financial-stress-index', 'us-interest-rate-spread'],
    tags: ['CMDI', '社債', 'ディストレス', 'NY Fed', '信用', 'クレジット', 'IG', 'HY', 'ハイイールド', '投資適格'],
  },

  // --- マーケット / 米国長短金利差 ---
  {
    indicatorId: 'us-interest-rate-spread',
    title: '米国長短金利差（イールドスプレッド）',
    country: 'market',
    category: 'equities',
    summary: '米国国債の長短金利差5種（2s10s, 3m10y, 5s30s, 10s30s, 3m2y）。逆イールドは景気後退の先行指標として注目される。',
    loadContent: loadMd('market/us-interest-rate-spread.md'),
    relatedIndicators: ['financial-stress-index', 'policy-rate'],
    tags: ['イールドカーブ', '逆イールド', '長短金利差', 'スプレッド', '2s10s', '3m10y', 'FRED', '国債', '利回り', 'スティープ', 'フラット'],
  },

  // --- マーケット / 国債利回り（債券）の見方 ---
  {
    indicatorId: 'us-treasury-yields',
    title: '国債利回り（債券）の見方',
    country: 'market',
    category: 'equities',
    summary: '名目金利・実質金利・BEI・タームプレミアムの分解、長期金利上昇の質の判定、入札の見方まで。',
    loadContent: loadMd('market/us-treasury-yields.md'),
    relatedIndicators: ['us-interest-rate-spread', 'term-premium', 'oas', 'policy-rate'],
    tags: ['国債', '利回り', '実質金利', 'TIPS', 'BEI', 'タームプレミアム', '入札', 'テール', '30年債', '10年債', '金', 'ゴールド'],
  },

  // --- マーケット / NAAIM ---
  {
    indicatorId: 'naaim',
    title: 'NAAIM Exposure Index',
    country: 'market',
    category: 'equities',
    summary: 'アクティブ運用者の米国株エクスポージャーを示す週次センチメント指標。実ポジションに近い情報から市場の偏りを把握。',
    loadContent: loadMd('market/naaim.md'),
    relatedIndicators: ['gex-dix', 'fear-greed'],
    tags: ['NAAIM', 'センチメント', 'エクスポージャー', 'アクティブ運用', 'ポジショニング'],
  },

  // --- マーケット / GEX・DIX ---
  {
    indicatorId: 'gex-dix',
    title: 'GEX / DIX',
    country: 'market',
    category: 'equities',
    summary: 'ガンマエクスポージャー（GEX）とダークインデックス（DIX）。オプションヘッジ構造による短期の値動き特性と、off-exchangeフローによる中期の需給の受け皿を把握する補助指標。',
    loadContent: loadMd('market/gex-dix.md'),
    relatedIndicators: ['sq-settlement', 'options-guide', 'nikkei-225'],
    tags: ['GEX', 'DIX', 'ガンマ', 'ダークプール', 'SqueezeMetrics', 'オプション', 'ヘッジ', 'マーケットメーカー'],
  },

  // --- マーケット / SQ ---
  {
    indicatorId: 'sq-settlement',
    title: 'SQ（特別清算指数）',
    country: 'market',
    category: 'equities',
    summary: '先物・オプションの最終決済に使われる特別清算指数。日本のメジャーSQ、米国のTriple Witching、幻のSQなど需給イベントとしての実務的な見方を解説。',
    loadContent: loadMd('market/sq-settlement.md'),
    relatedIndicators: ['nikkei-225', 'jpx-pcr', 'options-guide', 'anomaly-guide'],
    tags: ['SQ', 'メジャーSQ', 'Triple Witching', '特別清算', '先物', 'オプション', '限月', '幻のSQ', '裁定解消'],
  },

  // --- マーケット / CFTC ---
  {
    indicatorId: 'cftc-positioning',
    title: 'CFTCポジション動向',
    country: 'market',
    category: 'cot',
    summary: 'IMMポジションの偏りや極端な水準は転換点のシグナル。ポジの増減で新規・決済を読む。',
    loadContent: loadMd('market/cftc-positioning.md'),
    relatedIndicators: ['flow-knowledge', 'cot-usdjpy', 'cot-usd-index'],
    tags: ['CFTC', 'COT', 'IMM', 'ポジション', '投機筋', '実需筋', '先物'],
  },

  // --- マーケット / 円 ---
  {
    indicatorId: 'jpy',
    title: '円',
    country: 'market',
    category: 'forex',
    summary: '安全資産通貨と低金利・資源輸入国通貨の両面。年度末フロー、原油価格との関係、リスクオフ時の条件付き円高など。',
    loadContent: loadMd('market/jpy.md'),
    relatedIndicators: ['japan-fundamentals-yen', 'cot-usdjpy', 'cot-usd-index', 'flow-knowledge', 'rebalance'],
    tags: ['円', 'JPY', '安全資産', 'リスクオフ', '年度末', 'レパトリ', '原油', '交易条件', '日米金利差'],
  },

  // --- マーケット / 日本のファンダメンタルズと円 ---
  {
    indicatorId: 'japan-fundamentals-yen',
    title: '日本のファンダメンタルズと円相場',
    country: 'market',
    category: 'forex',
    summary: 'エネルギー・食料の輸入依存構造、円安の両面性、貿易赤字と経常黒字の関係、BOJ展望レポートの公表スケジュール、為替介入の仕組み・口先介入の表現強度・委託介入・実績公表まで。',
    loadContent: loadMd('market/japan-fundamentals-yen.md'),
    relatedIndicators: ['jpy', 'cot-usdjpy', 'boj-policy-rate-chart', 'terms-of-trade'],
    tags: ['日本', 'ファンダメンタルズ', '円', 'JPY', 'エネルギー依存', '食料自給率', '円安', '貿易赤字', '経常黒字', '為替介入', '外国為替平衡操作', '委託介入', '口先介入', 'BOJ', '展望レポート'],
  },

  // --- マーケット / ドル円 ---
  {
    indicatorId: 'cot-usdjpy',
    title: 'ドル円（USD/JPY）の見方',
    country: 'market',
    category: 'forex',
    summary: '仲値・五十日フロー、日米金利差、米国債利回りとの関係、キャリートレード巻き戻しに加え、投機筋の円ショート水準別（12万/14万/16万枚）の過熱判断とピークアウトの見方。',
    loadContent: loadMd('market/usdjpy.md'),
    relatedIndicators: ['jpy', 'japan-fundamentals-yen', 'cot-usd-index', 'cftc-positioning', 'us-interest-rate-spread', 'flow-knowledge'],
    tags: ['ドル円', 'USD/JPY', 'USDJPY', '仲値', '五十日', '日米金利差', 'キャリートレード', '円安', '円高', '為替', '円ショート', 'CFTC', 'IMM', 'ポジション', 'ピークアウト'],
  },

  // --- マーケット / ユーロ (EUR/USD) ---
  {
    indicatorId: 'cot-eurusd',
    title: 'ユーロ / EUR/USD',
    country: 'market',
    category: 'forex',
    summary: '米ドルに次ぐ国際通貨。EUR/USDは米欧の金利見通し・景気格差・ドル需要の相対比較で見る。',
    loadContent: loadMd('market/eurusd.md'),
    relatedIndicators: ['cot-usd-index', 'cot-eurgbp', 'cftc-positioning'],
    tags: ['ユーロ', 'EUR', 'EURUSD', 'ECB', '欧州', 'ドル', '金利差', '為替'],
  },

  // --- マーケット / ポンド (GBP/USD) ---
  {
    indicatorId: 'cot-gbpusd',
    title: 'ポンド / GBP/USD',
    country: 'market',
    category: 'forex',
    summary: 'リスク感応的な通貨としてのポンド。BoE政策見通し、エネルギー価格の複数経路、北海油田の実態。',
    loadContent: loadMd('market/gbpusd.md'),
    relatedIndicators: ['cot-eurgbp', 'cot-usd-index', 'cftc-positioning'],
    tags: ['ポンド', 'GBP', 'GBPUSD', 'BoE', '英国', '北海油田', 'エネルギー', 'リスク通貨', '為替'],
  },

  // --- マーケット / EUR/GBP ---
  {
    indicatorId: 'cot-eurgbp',
    title: 'EUR/GBP の見方',
    country: 'market',
    category: 'forex',
    summary: '英欧の相対比較を映す通貨ペア。金利差・政治・景気格差・エネルギー感応度の差で動きやすい。',
    loadContent: loadMd('market/eurgbp.md'),
    relatedIndicators: ['cot-eurusd', 'cot-gbpusd', 'cftc-positioning'],
    tags: ['EURGBP', 'ユーロポンド', 'ECB', 'BoE', '英欧', '相対比較', 'Brexit', '為替'],
  },

  // --- マーケット / 豪ドル (AUD/USD) ---
  {
    indicatorId: 'cot-audusd',
    title: '豪ドル（AUD）',
    country: 'market',
    category: 'forex',
    summary: '資源国通貨。鉄鉱石・石炭・LNG、中国景気、リスクセンチメントとの連動、金価格の位置づけ。',
    loadContent: loadMd('market/audusd.md'),
    relatedIndicators: ['cot-nzdusd', 'audnzd', 'cot-usd-index', 'cftc-positioning'],
    tags: ['豪ドル', 'AUD', 'AUDUSD', 'RBA', '鉄鉱石', '石炭', 'LNG', '中国', '資源国通貨', '為替'],
  },

  // --- マーケット / NZドル (NZD/USD) ---
  {
    indicatorId: 'cot-nzdusd',
    title: 'NZドル（NZD）',
    country: 'market',
    category: 'forex',
    summary: '農産物輸出国通貨。乳製品価格（GDT）、RBNZ政策、金利差とリスク選好。',
    loadContent: loadMd('market/nzdusd.md'),
    relatedIndicators: ['cot-audusd', 'audnzd', 'cot-usd-index', 'cftc-positioning'],
    tags: ['NZドル', 'NZD', 'NZDUSD', 'RBNZ', '乳製品', 'GDT', '農産物', '為替'],
  },

  // --- マーケット / AUD/NZD ---
  {
    indicatorId: 'audnzd',
    title: 'オージーニュージー（AUD/NZD）',
    country: 'market',
    category: 'forex',
    summary: '豪NZの相対比較ペア。RBA vs RBNZ政策差、資源価格 vs 乳製品価格、中国要因。',
    loadContent: loadMd('market/audnzd.md'),
    relatedIndicators: ['cot-audusd', 'cot-nzdusd', 'cftc-positioning'],
    tags: ['AUDNZD', 'オージーニュージー', 'RBA', 'RBNZ', '鉄鉱石', '乳製品', '相対比較', '為替'],
  },

  // --- マーケット / カナダドル (USD/CAD) ---
  {
    indicatorId: 'cot-usdcad',
    title: 'カナダドル（CAD）',
    country: 'market',
    category: 'forex',
    summary: '原油・米国景気・米加金利差の三本柱。米国への輸出依存度71.7%、エネルギー純輸出国。',
    loadContent: loadMd('market/usdcad.md'),
    relatedIndicators: ['cot-usd-index', 'cot-audusd', 'cftc-positioning'],
    tags: ['カナダドル', 'CAD', 'USDCAD', 'BoC', '原油', '米国', 'エネルギー', '資源国通貨', '為替'],
  },

  // --- マーケット / 米ドル ---
  {
    indicatorId: 'cot-usd-index',
    title: '米ドル',
    country: 'market',
    category: 'forex',
    summary: '基軸通貨としての米ドルの性質。リスクオフ・リスクオンの両局面でのドルの振る舞い、金利差・資本フロー・ドル資金需給の見方。',
    loadContent: loadMd('market/usd.md'),
    relatedIndicators: ['cftc-positioning', 'us-interest-rate-spread', 'term-premium'],
    tags: ['米ドル', 'USD', 'DXY', 'ドルインデックス', '基軸通貨', 'リスクオフ', 'BIS', 'FRB', '為替'],
  },

  // --- マーケット / 金（ゴールド） ---
  {
    indicatorId: 'cot-gold',
    title: '金（ゴールド）',
    country: 'market',
    category: 'commodities',
    summary: '実質金利・ドル・地政学リスク・中央銀行買いで動く。インフレヘッジだけでなく準備資産・信用不安ヘッジとしての側面。',
    loadContent: loadMd('market/gold.md'),
    relatedIndicators: ['comex-gold-inventory', 'gold-premium', 'cot-usd-index', 'us-treasury-yields', 'cftc-positioning'],
    tags: ['金', 'ゴールド', 'Gold', 'XAUUSD', '実質金利', 'TIPS', 'BEI', 'インフレ', '中央銀行', '安全資産'],
  },

  // --- マーケット / COMEX金在庫 ---
  {
    indicatorId: 'comex-gold-inventory',
    title: 'COMEX金在庫（Eligible / Registered / Pledged）',
    country: 'market',
    category: 'commodities',
    summary: 'Eligible・Registered・Pledgedの区分と実務上の読み方。受渡し逼迫や現物需給の強さをRegistered在庫で判断する。',
    loadContent: loadMd('market/comex-gold-inventory.md'),
    relatedIndicators: ['cot-gold', 'gold-premium', 'cftc-positioning'],
    tags: ['COMEX', '金在庫', 'Eligible', 'Registered', 'Pledged', 'warrant', '受渡し', 'ゴールド', '現物需給'],
  },

  // --- マーケット / 金プレミアム ---
  {
    indicatorId: 'gold-premium',
    title: '金プレミアム（中国・インド）',
    country: 'market',
    category: 'commodities',
    summary: '中国（SGE）とインド（着地原価）の金プレミアム/ディスカウント。現物需給のバランスを映す。',
    loadContent: loadMd('market/gold-premium.md'),
    relatedIndicators: ['cot-gold', 'comex-gold-inventory', 'cftc-positioning'],
    tags: ['金プレミアム', 'ゴールド', '中国', 'インド', 'SGE', 'WGC', '現物需給', 'ディスカウント'],
  },

  // --- マーケット / 銀 ---
  {
    indicatorId: 'cot-silver',
    title: '銀（シルバー）',
    country: 'market',
    category: 'commodities',
    summary: '工業金属＋貴金属の二面性。金価格・ドル・景気・工業需要・需給赤字の順で確認。',
    loadContent: loadMd('market/silver.md'),
    relatedIndicators: ['cot-gold', 'gold-premium', 'cftc-positioning'],
    tags: ['銀', 'シルバー', 'Silver', '工業金属', '貴金属', '太陽光', 'PV', 'ETF', '需給赤字'],
  },

  // --- マーケット / 銅 ---
  {
    indicatorId: 'cot-copper',
    title: '銅（カッパー）',
    country: 'market',
    category: 'commodities',
    summary: '景気の体温計。中国需要58%。景気循環だけでなく電力網投資・EV・供給制約も価格形成に影響。',
    loadContent: loadMd('market/copper.md'),
    relatedIndicators: ['copper-to-gold-ratio', 'cot-gold', 'cot-silver', 'cftc-positioning'],
    tags: ['銅', 'カッパー', 'Copper', '工業金属', '中国', '景気', 'EV', '電力網', 'LME', 'COMEX', 'SHFE'],
  },

  // --- マーケット / 銅金レシオ ---
  {
    indicatorId: 'copper-to-gold-ratio',
    title: '銅金レシオ',
    country: 'market',
    category: 'commodities',
    summary: '銅/金の比率。景気回復期待 vs 安全資産需要のバランスを映す温度計。単独判断は不可。',
    loadContent: loadMd('market/copper-to-gold-ratio.md'),
    relatedIndicators: ['cot-copper', 'cot-gold', 'global-manufacturing-pmi'],
    tags: ['銅金レシオ', 'Copper Gold Ratio', '景気', 'リスクオン', 'リスクオフ', '金利', '中国'],
  },

  // --- マーケット / 原油 ---
  {
    indicatorId: 'cot-crude-oil',
    title: '原油',
    country: 'market',
    category: 'energy',
    summary: '需要要因か供給要因かを切り分ける。OPEC+・余剰能力・先物カーブ・地政学リスクの順で確認。',
    loadContent: loadMd('market/crude-oil.md'),
    relatedIndicators: ['weekly-crude-oil-inventories', 'shale-oil-rig-count', 'ism-manufacturing', 'global-manufacturing-pmi', 'cftc-positioning'],
    tags: ['原油', 'WTI', 'Brent', 'OPEC', '地政学', 'ホルムズ', 'バックワーデーション', 'コンタンゴ'],
  },

  // --- マーケット / 週間原油在庫 ---
  {
    indicatorId: 'weekly-crude-oil-inventories',
    title: '週間原油在庫',
    country: 'market',
    category: 'energy',
    summary: 'EIA週次レポート。在庫・製油所稼働率・製品在庫をセットで確認。',
    loadContent: loadMd('market/weekly-crude-oil-inventories.md'),
    relatedIndicators: ['cot-crude-oil', 'shale-oil-rig-count'],
    tags: ['原油在庫', 'EIA', 'ガソリン在庫', '留出油在庫', '稼働率', '週次'],
  },

  // --- マーケット / シェールオイル・リグ稼働数 ---
  {
    indicatorId: 'shale-oil-rig-count',
    title: 'シェールオイル生産量・リグ稼働数',
    country: 'market',
    category: 'energy',
    summary: 'リグ数だけでは不十分。完了井戸、井戸あたり生産性もセットで確認。',
    loadContent: loadMd('market/shale-oil-rig-count.md'),
    relatedIndicators: ['cot-crude-oil', 'weekly-crude-oil-inventories'],
    tags: ['シェール', 'リグ', 'Baker Hughes', 'EIA', '生産量', '完了井戸'],
  },

  // --- マーケット / 天然ガス ---
  {
    indicatorId: 'cot-natural-gas',
    title: '天然ガス',
    country: 'market',
    category: 'energy',
    summary: '季節性とインフラ制約の強い地域型エネルギー。天候・在庫・LNG設備・地域間価格差が価格の中心。',
    loadContent: loadMd('market/natural-gas.md'),
    relatedIndicators: ['cot-crude-oil', 'shale-oil-rig-count'],
    tags: ['天然ガス', 'Natural Gas', 'LNG', 'Henry Hub', 'TTF', 'JKM', '在庫', '暖房', 'EIA', 'メタン'],
  },

  // --- マーケット / S&P GSCI ---
  {
    indicatorId: 'sp-gsci',
    title: 'S&P GSCI',
    country: 'market',
    category: 'commodities',
    summary: 'エネルギー比重が大きい総合商品指数。エネルギー主導のインフレ圧力や商品市況の変化を広く把握する際の参考指標。',
    loadContent: loadMd('market/sp-gsci.md'),
    relatedIndicators: ['cot-crude-oil', 'cot-natural-gas', 'cot-copper'],
    tags: ['GSCI', 'S&P', '商品指数', 'エネルギー', 'コモディティ', '原油', 'インフレ'],
  },

  // --- マーケット / MSCI中国 ---
  {
    indicatorId: 'msci-china',
    title: 'MSCI中国株価指数',
    country: 'market',
    category: 'equities',
    summary: '中国関連株式の値動きを把握する指数。中国景気・政策期待・不動産・信用環境を幅広く反映。',
    loadContent: loadMd('market/msci-china.md'),
    relatedIndicators: ['cot-copper', 'copper-to-gold-ratio'],
    tags: ['MSCI', '中国', 'China', '中国株', '不動産', 'PMI', '新興国'],
  },

  // --- グローバル / バルチック海運指数 ---
  {
    indicatorId: 'baltic-dry-index',
    title: 'バルチック海運指数（BDI）',
    country: 'global',
    category: 'economy',
    summary: '乾貨物海上輸送のスポット運賃指数。原材料輸送需要を通じて世界景気や貿易活動の温度感を映す補助指標。',
    loadContent: loadMd('global/baltic-dry-index.md'),
    relatedIndicators: ['global-manufacturing-pmi', 'cot-copper'],
    tags: ['BDI', 'バルチック', '海運', 'ドライバルク', '鉄鉱石', '中国', 'PPI', '景気先行'],
  },

  // --- マーケット / フロー ---
  {
    indicatorId: 'flow-knowledge',
    title: 'フロー（資金フロー・市場のクセ）',
    country: 'market',
    category: 'flow',
    summary: 'リスクオフ・デレバレッジ・月末fix・仲値フロー・緩和局面の相関歪みなど、実務で意識すべき資金フローの知識。',
    loadContent: loadMd('market/flow-knowledge.md'),
    relatedIndicators: ['cftc-positioning', 'rebalance'],
    tags: ['フロー', 'リスクオフ', '月末', 'ロンドンfix', '仲値', '五十日', 'デレバレッジ', '緩和'],
  },

  // --- マーケット / リバランス ---
  {
    indicatorId: 'rebalance',
    title: 'リバランス（月末・四半期末・半期末）',
    country: 'market',
    category: 'rebalance',
    summary: '月末・四半期末・半期末のヘッジ調整フロー。ロンドン4pm fix周辺のフロー集中と実務上の見方。',
    loadContent: loadMd('market/rebalance.md'),
    relatedIndicators: ['flow-knowledge', 'cftc-positioning'],
    tags: ['リバランス', '月末', '四半期末', '半期末', 'ロンドンfix', 'ヘッジ調整'],
  },

  // --- マーケット / アノマリー ---
  {
    indicatorId: 'anomaly-guide',
    title: 'アノマリー活用ガイド',
    country: 'market',
    category: 'anomaly',
    summary: '月末月初効果、Sell in May、FOMC日効果、ゴトー日、エネルギー季節性など、実務で使えるアノマリーをランク別に整理。',
    loadContent: loadMd('market/anomaly-guide.md'),
    relatedIndicators: ['flow-knowledge', 'rebalance', 'cftc-positioning'],
    tags: ['アノマリー', 'シーズナリティ', '季節性', '月末月初', 'Sell in May', 'FOMC', 'ゴトー日', 'サンタクロースラリー'],
  },

  // --- マーケット / オプション ---
  {
    indicatorId: 'options-guide',
    title: 'オプションとは何か',
    country: 'market',
    category: 'options',
    summary: 'オプションの基礎知識。コール・プット、ITM/ATM/OTM、デルタ、IVの概念を解説。',
    loadContent: loadMd('market/options-guide.md'),
    relatedIndicators: ['forex-iv', 'ny-option-cut', 'options-tradingview'],
    tags: ['オプション', 'コール', 'プット', 'IV', 'デルタ', 'ボラティリティ'],
  },
  {
    indicatorId: 'ny-option-cut',
    title: 'NYオプションカット',
    country: 'market',
    category: 'options',
    summary: '毎日NY10:00 AMに設定される為替オプションの権利行使期限。大口ポジションが為替レートに影響。',
    loadContent: loadMd('market/ny-option-cut.md'),
    relatedIndicators: ['forex-iv', 'options-guide'],
    tags: ['オプションカット', 'バリア', '為替', 'FX', 'ピンニング'],
  },
  {
    indicatorId: 'forex-iv',
    title: '為替オプションIV',
    country: 'market',
    category: 'options',
    summary: '為替オプション市場のインプライド・ボラティリティ。方向別リスクの織り込みを確認。',
    loadContent: loadMd('market/forex-iv.md'),
    relatedIndicators: ['ny-option-cut', 'options-guide'],
    tags: ['IV', 'ボラティリティ', '為替', 'FX', 'スキュー', 'スマイル'],
  },
  {
    indicatorId: 'options-tradingview',
    title: 'オプションの見方（TradingView）',
    country: 'market',
    category: 'options',
    summary: 'TradingViewのオプション画面の読み方。チェーン・ボラティリティカーブ・ギリシャ指標の解説。',
    loadContent: loadMd('market/options-tradingview.md'),
    relatedIndicators: ['options-guide', 'forex-iv'],
    tags: ['TradingView', 'オプション', 'チェーン', 'ギリシャ指標', 'ボラティリティカーブ'],
  },
  {
    indicatorId: 'nt-magnification',
    title: 'NT倍率（日経平均 / TOPIX）',
    country: 'market',
    category: 'equities',
    summary: '日経平均をTOPIXで割った比率。値がさ株主導か市場全体に買いが広がっているかを見る補助指標。',
    loadContent: loadMd('market/nt-magnification.md'),
    relatedIndicators: ['jpx-investor-trading', 'jpx-pcr', 'nikkei-225', 'topix'],
    tags: ['NT倍率', '日経平均', 'TOPIX', '値がさ株', '裁定取引', '日本株'],
  },
  {
    indicatorId: 'eps-per-earnings-yield',
    title: 'EPS・PER・株式益利回り',
    country: 'market',
    category: 'equities',
    summary: 'EPS、PER、株式益利回りの定義と実務的な使い方。株価をEPS要因とPER要因に分解する見方。ISM前年差と予想EPS前年比の関係。',
    loadContent: loadMd('market/eps-per-earnings-yield.md'),
    relatedIndicators: ['nikkei-225', 'topix', 'ism-manufacturing'],
    tags: ['EPS', 'PER', '益利回り', 'バリュエーション', '株式', 'イールドスプレッド', 'ISM', '予想EPS', '前年比'],
  },
  {
    indicatorId: 'growth-value-ratio',
    title: '米国株のバリュー株・グロース株の見方',
    country: 'market',
    category: 'equities',
    summary: '主要指数の特性、Style指数、実質金利との関係、セクター特性、Equal Weightとの比較など、グロース/バリューの実務的な見方。',
    loadContent: loadMd('market/growth-value-ratio.md'),
    relatedIndicators: ['russell2000-russell1000', 'sector-ratio', 'sp500-stock-portion'],
    tags: ['グロース', 'バリュー', 'Growth', 'Value', 'IVW', 'IVE', 'Style', 'Nasdaq', 'Russell', '実質金利'],
  },
  {
    indicatorId: 'sector-ratio',
    title: '米株セクター別の見方',
    country: 'market',
    category: 'equities',
    summary: 'GICS分類に基づくセクター特性、景気サイクルとセクターローテーション、原油・金利との関係、XLY/XLPの相対比較など実務的な見方。',
    loadContent: loadMd('market/sector-ratio.md'),
    relatedIndicators: ['growth-value-ratio', 'russell2000-russell1000', 'sp500-stock-portion'],
    tags: ['セクター', 'XLY', 'XLP', 'XLF', 'XLU', 'GICS', 'ローテーション', '景気サイクル', 'エネルギー', '金融'],
  },
  {
    indicatorId: 'sector-cycle',
    title: '米株サイクル',
    country: 'market',
    category: 'equities',
    summary: '景気循環の各局面（回復・拡大・減速・後退）で相対的に強くなりやすいセクターの整理。エネルギー・通信サービス・不動産の扱いも解説。',
    loadContent: loadMd('market/sector-cycle.md'),
    relatedIndicators: ['sector-ratio', 'growth-value-ratio', 'russell2000-russell1000'],
    tags: ['セクターローテーション', '景気循環', 'サイクル', 'ディフェンシブ', '景気敏感', 'Fidelity', 'State Street', 'GICS'],
  },
  {
    indicatorId: 'vix-term-structure',
    title: 'ボラティリティ指数の見方',
    country: 'market',
    category: 'equities',
    summary: 'VIXの意味、期間構造（コンタンゴ/バックワーデーション）、実務での読み方。方向予測ではなく変動幅の指標として使う考え方。',
    loadContent: loadMd('market/vix-term-structure.md'),
    relatedIndicators: ['gex-dix', 'options-guide', 'fear-greed'],
    tags: ['VIX', 'ボラティリティ', 'コンタンゴ', 'バックワーデーション', 'Cboe', '期間構造', 'VIX9D', 'VIX3M'],
  },
  {
    indicatorId: 'advance-decline-ratio',
    title: '騰落レシオ',
    country: 'market',
    category: 'equities',
    summary: '東証プライム市場の値上がり・値下がり銘柄数から市場の広がり（breadth）を見る指標。',
    loadContent: loadMd('market/advance-decline-ratio.md'),
    relatedIndicators: ['jpx-investor-trading', 'nt-magnification', 'nikkei-225', 'topix'],
    tags: ['騰落レシオ', '市場breadth', '過熱感', '東証プライム', '日本株'],
  },

  // --- マーケット / 相関関係 ---
  {
    indicatorId: 'correlation-guide',
    title: '相関関係',
    country: 'market',
    category: 'correlation',
    summary: 'ドル・ユーロ・金、株価と為替、資源国通貨と商品、金利と株式・債券など、主要資産間の相関関係の実務的な整理。',
    loadContent: loadMd('market/correlation-guide.md'),
    relatedIndicators: ['copper-to-gold-ratio', 'sp-gsci', 'growth-value-ratio', 'flow-knowledge'],
    tags: ['相関', '逆相関', 'ドル', 'ユーロ', '金', '株式', '債券', '豪ドル', '加ドル', '資源国', '中国', 'リスクオフ'],
  },

  // --- マーケット / 景気サイクル ---
  {
    indicatorId: 'business-cycle',
    title: '景気サイクル',
    country: 'market',
    category: 'economy',
    summary: '回復→拡大→後期→後退の各局面で優位になりやすい資産・セクターの整理。イールドカーブとLEIの実務的な使い方。',
    loadContent: loadMd('market/business-cycle.md'),
    relatedIndicators: ['sector-cycle', 'sector-ratio', 'correlation-guide', 'growth-value-ratio'],
    tags: ['景気サイクル', '景気循環', 'LEI', 'イールドカーブ', '逆イールド', 'ディフェンシブ', '景気敏感', '債券', 'セクターローテーション'],
  },

  // --- マーケット / 経済サイクルと主要資産 ---
  {
    indicatorId: 'economic-cycle-assets',
    title: '経済サイクルと主要資産の関係',
    country: 'market',
    category: 'economy',
    summary: '景気拡大・後退・インフレ・デフレの各局面で株式・債券・商品がどう動きやすいかの整理。ドルと商品、株債券の相関変化も解説。',
    loadContent: loadMd('market/economic-cycle-assets.md'),
    relatedIndicators: ['business-cycle', 'correlation-guide', 'sector-cycle', 'sp-gsci'],
    tags: ['経済サイクル', '株式', '債券', '商品', 'インフレ', 'ディスインフレ', 'デフレ', 'ドル', '信用スプレッド', 'イールドカーブ'],
  },

  // --- マーケット / 相場サイクル ---
  {
    indicatorId: 'market-cycle',
    title: '相場サイクル',
    country: 'market',
    category: 'economy',
    summary: '金融相場→業績相場→逆金融相場→逆業績相場の4局面。金利・景気・業績・市場の織り込みから相場の現在地を判断する枠組み。',
    loadContent: loadMd('market/market-cycle.md'),
    relatedIndicators: ['business-cycle', 'economic-cycle-assets', 'correlation-guide', 'sector-cycle'],
    tags: ['相場サイクル', '金融相場', '業績相場', '逆金融相場', '逆業績相場', '金利', '利下げ', '利上げ', '為替', 'PER'],
  },

  // --- マーケット / ファンダメンタルズ概要 ---
  {
    indicatorId: 'fundamentals-overview',
    title: 'ファンダメンタルズ概要',
    country: 'market',
    category: 'economy',
    summary: '金融政策と財政政策を軸にしたファンダメンタルズの見方。需要・供給インフレの区別、減税効果、政策レジーム、為替介入、原油減産の整理。',
    loadContent: loadMd('market/fundamentals-overview.md'),
    relatedIndicators: ['market-cycle', 'business-cycle', 'economic-cycle-assets', 'correlation-guide'],
    tags: ['ファンダメンタルズ', '金融政策', '財政政策', '減税', 'インフレ', '為替介入', 'OPEC', '減産', '政策レジーム', '中央銀行'],
  },

  // --- グローバル / Komtrax ---
  {
    indicatorId: 'komatrax',
    title: 'Komtrax（車両稼働時間）',
    country: 'global',
    category: 'economy',
    summary: 'コマツ建機の地域別月次稼働時間。建設活動・インフラ投資・資源需要の現場感を把握する先行的な補助指標。',
    loadContent: loadMd('global/komtrax.md'),
    relatedIndicators: ['global-manufacturing-pmi', 'baltic-dry-index'],
    tags: ['Komtrax', 'コマツ', '建設機械', '稼働時間', '建設投資', 'インフラ', '景気先行'],
  },

  // --- グローバル / OECD CLI ---
  {
    indicatorId: 'oecd-cli',
    title: 'OECD景気先行指数（CLI）',
    country: 'global',
    category: 'economy',
    summary: '景気循環の転換点を6～9か月先取りすることを目標とした先行指標。水準より方向と転換点を重視して読む。',
    loadContent: loadMd('global/oecd-cli.md'),
    relatedIndicators: ['global-manufacturing-pmi', 'baltic-dry-index', 'komatrax'],
    tags: ['OECD', 'CLI', '景気先行指数', 'G20', 'G7', '転換点', '景気循環'],
  },

  // --- グローバル / コンテナ運賃指数 ---
  {
    indicatorId: 'container-freight-index',
    title: 'コンテナ運賃指数',
    country: 'global',
    category: 'economy',
    summary: '海上コンテナ輸送のスポット運賃指数。世界貿易・物流逼迫度・航路障害・環境規制の影響を映す補助指標。',
    loadContent: loadMd('global/container-freight-index.md'),
    relatedIndicators: ['baltic-dry-index', 'oecd-cli', 'global-manufacturing-pmi'],
    tags: ['SCFI', 'コンテナ', '運賃', '海運', '物流', '紅海', 'スエズ', 'パナマ', '環境規制', 'IMO'],
  },

  // --- グローバル / 台湾製造業PMI ---
  {
    indicatorId: 'taiwan-manufacturing-pmi',
    title: '台湾製造業PMI',
    country: 'global',
    category: 'economy',
    summary: '電子部品・半導体比重の大きい台湾製造業の景況感指数。世界の半導体・AIハードウェア・アジア輸出製造業サイクルを読む補助指標。',
    loadContent: loadMd('global/taiwan-manufacturing-pmi.md'),
    relatedIndicators: ['taiwan-export-orders', 'korea-exports', 'global-manufacturing-pmi'],
    tags: ['台湾', 'PMI', '製造業', '半導体', '電子部品', 'TSMC', 'AI'],
  },

  // --- グローバル / 台湾輸出受注 ---
  {
    indicatorId: 'taiwan-export-orders',
    title: '台湾輸出受注',
    country: 'global',
    category: 'economy',
    summary: '台湾経済部が月次公表する輸出受注統計。SOX→台湾輸出受注→ISM→中国在庫の波及の流れで需要変化を早期に捉える先行指標。',
    loadContent: loadMd('global/taiwan-export-orders.md'),
    relatedIndicators: ['ism-manufacturing', 'cn-electronics-stock', 'taiwan-manufacturing-pmi', 'korea-exports', 'semiconductor-sales'],
    tags: ['台湾', '輸出受注', '半導体', '電子部品', '先行指標', 'MOEA', 'SOX', 'ISM', 'エレクトロニクス循環'],
  },

  // --- グローバル / 韓国輸出 ---
  {
    indicatorId: 'korea-exports',
    title: '韓国輸出',
    country: 'global',
    category: 'economy',
    summary: '韓国税関の月次輸出統計。半導体・ICT中心で世界の電子需要やアジア製造業の地合いを早期に確認できる。',
    loadContent: loadMd('global/korea-exports.md'),
    relatedIndicators: ['taiwan-manufacturing-pmi', 'taiwan-export-orders', 'global-manufacturing-pmi'],
    tags: ['韓国', '輸出', '半導体', 'ICT', 'ディスプレー', 'アジア', '貿易'],
  },

  // --- マーケット / MMF ---
  {
    indicatorId: 'mmf',
    title: 'MMF（マネー・マーケット・ファンド）',
    country: 'market',
    category: 'flow',
    summary: '短期高流動性資産で運用される投資信託。残高の増減はリスク回避だけでなく金利環境・流動性需要も反映する。',
    loadContent: loadMd('market/mmf.md'),
    relatedIndicators: ['flow-knowledge', 'fundamentals-overview', 'correlation-guide'],
    tags: ['MMF', 'マネーマーケット', '待機資金', 'リスク回避', '政府系', 'プライム', 'ON RRP', '流動性', '短期金利'],
  },

  // --- グローバル / 半導体売上高 ---
  {
    indicatorId: 'semiconductor-sales',
    title: '半導体売上高（WSTS）',
    country: 'global',
    category: 'economy',
    summary: 'TSMC月次売上・台湾PMI先行き・SOX前年比と世界半導体売上高の関係。半導体サイクルの先行・同時・遅行指標の使い分け。',
    loadContent: loadMd('global/semiconductor-sales.md'),
    relatedIndicators: ['tsmc-revenue', 'taiwan-pmi-outlook', 'sox-yoy', 'taiwan-manufacturing-pmi', 'taiwan-export-orders', 'cn-electronics-stock'],
    tags: ['半導体', 'WSTS', 'TSMC', 'SOX', 'PMI', '台湾', '半導体サイクル', 'AI'],
  },

  // --- マーケット / TSMC売上高 ---
  {
    indicatorId: 'tsmc-revenue',
    title: 'TSMC月次売上高',
    country: 'market',
    category: 'equities',
    summary: 'TSMCの月次売上は半導体サイクルの同時確認～やや遅行する指標。先端ロジック・AI関連の影響が強い。',
    loadContent: loadMd('market/tsmc-revenue.md'),
    relatedIndicators: ['semiconductor-sales', 'taiwan-pmi-outlook', 'sox-yoy'],
    tags: ['TSMC', '売上高', '半導体', 'ファウンドリー', '台湾', 'AI', '先端ロジック'],
  },

  // --- グローバル / 台湾PMI先行き ---
  {
    indicatorId: 'taiwan-pmi-outlook',
    title: '台湾PMI先行き（電子工学業）',
    country: 'global',
    category: 'economy',
    summary: '半導体・電子部品の受注見通しを比較的早く反映。世界半導体売上高に1～4か月先行しやすい先行確認指標。',
    loadContent: loadMd('global/taiwan-pmi-outlook.md'),
    relatedIndicators: ['semiconductor-sales', 'tsmc-revenue', 'sox-yoy'],
    tags: ['台湾', 'PMI', '電子工学', '半導体', '先行指標', 'CIER'],
  },

  // --- マーケット / SOX前年比 ---
  {
    indicatorId: 'sox-yoy',
    title: 'SOX前年比と世界半導体売上高',
    country: 'market',
    category: 'equities',
    summary: 'SOX指数前年比は世界半導体売上高に2～4か月先行しやすい。市場が半導体サイクルの回復を先読みしているかを確認する指標。',
    loadContent: loadMd('market/sox-yoy.md'),
    relatedIndicators: ['semiconductor-sales', 'tsmc-revenue', 'taiwan-pmi-outlook'],
    tags: ['SOX', '半導体', 'フィラデルフィア', '前年比', '先行指標', '株価指数'],
  },

  // --- マーケット / GDP ---
  {
    indicatorId: 'gdp',
    title: 'GDP（国内総生産）',
    country: 'market',
    category: 'economy',
    summary: '一定期間内に国内で生産された付加価値総額。実質GDPで景気の実勢を、内訳で成長の質と持続性を判断する基本指標。',
    loadContent: loadMd('market/gdp.md'),
    relatedIndicators: ['gdp-growth', 'quarterly-gdp', 'ism-manufacturing'],
    tags: ['GDP', '国内総生産', '実質GDP', '名目GDP', 'GDPデフレーター', '景気後退', 'NBER', '個人消費', '設備投資'],
  },

  // --- マーケット / 鉱工業生産 ---
  {
    indicatorId: 'industrial-production',
    title: '鉱工業生産',
    country: 'market',
    category: 'economy',
    summary: '製造業・鉱業・公益の生産動向を指数化した一致系指標。景気の現状把握や転換点の確認に広く用いられる。',
    loadContent: loadMd('market/industrial-production.md'),
    relatedIndicators: ['gdp', 'ism-manufacturing'],
    tags: ['鉱工業生産', 'Industrial Production', '製造業', '設備稼働率', '一致指標', '景気循環', 'FRB'],
  },

  // --- USA / 設備稼働率 ---
  {
    indicatorId: 'capacity-utilization',
    title: '設備稼働率',
    country: 'usa',
    category: 'economy',
    summary: '工業部門の生産能力に対する実際の生産比率。需給逼迫度、設備投資の先行き、インフレ圧力の強弱を確認する補助指標。',
    loadContent: loadMd('usa/capacity-utilization.md'),
    relatedIndicators: ['industrial-production', 'ism-manufacturing', 'gdp'],
    tags: ['設備稼働率', 'Capacity Utilization', 'FRB', '製造業', '鉱業', '供給制約', 'インフレ圧力', '設備投資'],
  },

  // --- USA / FCI-G ---
  {
    indicatorId: 'fci',
    title: 'FCI-G（金融情勢指数）',
    country: 'usa',
    category: 'economy',
    summary: 'FRBが7系列の金融変数から算出する成長インパルス指標。金融環境が今後1年のGDP成長率に与える追い風・逆風の方向と強さを把握する。',
    loadContent: loadMd('usa/fci.md'),
    relatedIndicators: ['nfci', 'bank-lending', 'gdp', 'oas'],
    tags: ['FCI-G', '金融情勢指数', 'Financial Conditions', 'FRB', 'GDP', '金融環境', '金利', '社債', '株価', '住宅価格', 'ドル'],
  },

  // --- USA / NFCI ---
  {
    indicatorId: 'nfci',
    title: 'シカゴ連銀金融環境指数（NFCI）',
    country: 'usa',
    category: 'economy',
    summary: 'シカゴ連銀が週次で公表する総合金融環境指数。リスク・信用・レバレッジの3面から金融環境の引き締まり・緩和を総合的に把握する。',
    loadContent: loadMd('usa/nfci.md'),
    relatedIndicators: ['fci', 'bank-lending', 'gdp'],
    tags: ['NFCI', 'シカゴ連銀', '金融環境指数', 'Financial Conditions', 'リスク', '信用', 'レバレッジ'],
  },

  // --- USA / 銀行貸し出し態度（SLOOS） ---
  {
    indicatorId: 'bank-lending',
    title: '銀行貸し出し態度（SLOOS）',
    country: 'usa',
    category: 'economy',
    summary: 'FRBが四半期ごとに公表する融資基準・融資需要の調査。信用供給と信用需要の変化から景気の先行きを把握する金融環境指標。',
    loadContent: loadMd('usa/bank-lending.md'),
    relatedIndicators: ['gdp', 'fci', 'nfci'],
    tags: ['SLOOS', '銀行貸出態度', 'Senior Loan Officer', '融資基準', '信用供給', 'C&I', 'CRE', '商業不動産', 'FRB'],
  },

  // --- USA / 消費 ---
  {
    indicatorId: 'retail-sales',
    title: '小売売上高',
    country: 'usa',
    category: 'consumer',
    summary: 'Census Bureauが公表する月次の名目小売売上高。コントロールグループが基調需要の把握に最も有用で、PCE・GDPの基礎データとしても重要。',
    loadContent: loadMd('usa/retail-sales.md'),
    relatedIndicators: ['pce-deflator', 'gdp'],
    tags: ['小売売上高', 'Retail Sales', 'コントロールグループ', 'Census Bureau', '個人消費', 'PCE', '財消費'],
  },

  {
    indicatorId: 'redbook',
    title: 'レッドブック（Johnson Redbook Index）',
    country: 'usa',
    category: 'consumer',
    summary: '大手総合小売の同店売上高を週次で集計した民間指標。公式小売売上高に先行して個人消費の温度感を確認できる。',
    loadContent: loadMd('usa/redbook.md'),
    relatedIndicators: ['retail-sales', 'pce', 'cb-consumer-confidence'],
    tags: ['レッドブック', 'Redbook', '小売', '同店売上', '週次', '個人消費', 'Johnson Redbook'],
  },

  {
    indicatorId: 'affinity-spend',
    title: '全米クレカ消費額（Affinity系列）',
    country: 'usa',
    category: 'consumer',
    summary: 'Affinity Solutionsのカード支出データを基にした高頻度消費トラッカー。公式統計の公表前に消費の方向感を探る補助指標。',
    loadContent: loadMd('usa/affinity-spend.md'),
    relatedIndicators: ['retail-sales', 'pce', 'redbook'],
    tags: ['Affinity', 'クレジットカード', 'デビットカード', 'カード支出', '高頻度', '個人消費', 'Economic Tracker', 'Opportunity Insights'],
  },

  {
    indicatorId: 'cb-consumer-confidence',
    title: 'CB消費者信頼感指数',
    country: 'usa',
    category: 'consumer',
    summary: 'The Conference Boardの消費者調査。現況指数と期待指数を分けて見ることで、家計心理の同時性と先行性の両面を把握できる。',
    loadContent: loadMd('usa/cb-consumer-confidence.md'),
    relatedIndicators: ['retail-sales', 'pce-deflator'],
    tags: ['消費者信頼感', 'Consumer Confidence', 'Conference Board', '期待指数', '現況指数', '個人消費', '家計心理'],
  },

  {
    indicatorId: 'personal-saving-rate',
    title: '家計貯蓄率（米国）',
    country: 'usa',
    category: 'consumer',
    summary: '可処分所得のうち消費に回さず残した割合。フロー（貯蓄率）とストック（貯蓄残高）の混同に注意。上昇は消費抑制、低下は支出姿勢の強まりを示唆。',
    loadContent: loadMd('usa/personal-saving-rate.md'),
    relatedIndicators: ['disposable-income', 'pce', 'cb-consumer-confidence'],
    tags: ['貯蓄率', 'Personal Saving Rate', 'BEA', '可処分所得', '消費', '家計'],
  },
  {
    indicatorId: 'disposable-income',
    title: '可処分所得（米国）',
    country: 'usa',
    category: 'consumer',
    summary: '家計が消費か貯蓄に配分できる所得。名目ではなく実質可処分所得で購買力の変化を見ることが重要。',
    loadContent: loadMd('usa/disposable-income.md'),
    relatedIndicators: ['personal-saving-rate', 'pce', 'cb-consumer-confidence'],
    tags: ['可処分所得', 'Disposable Income', 'BEA', 'FRED', '実質所得', '購買力', '消費'],
  },
  {
    indicatorId: 'pce',
    title: '個人消費支出（PCE）',
    country: 'usa',
    category: 'consumer',
    summary: 'BEAの個人消費支出。実質PCEで物価変動を除いた消費量の変化を確認でき、財消費とサービス消費のバランスまで見ると精度が高まる。',
    loadContent: loadMd('usa/pce.md'),
    relatedIndicators: ['pce-deflator', 'retail-sales', 'disposable-income', 'personal-saving-rate'],
    tags: ['PCE', '個人消費', 'BEA', '実質消費', '財消費', 'サービス消費'],
  },

  // --- USA / 住宅 ---
  {
    indicatorId: 'mortgage-rates',
    title: '住宅ローン金利（フレディ・マック30年固定）',
    country: 'usa',
    category: 'housing',
    summary: '住宅ローン金利は住宅需要を大きく左右する。6％前後がaffordabilityの節目。PMMS調査の前提条件、rate lock-in effectによる在庫への影響も含む。',
    loadContent: loadMd('usa/mortgage-rates.md'),
    relatedIndicators: ['existing-home-sales', 'housing-starts-permits', 'redfin-case-shiller'],
    tags: ['住宅ローン金利', 'Mortgage Rate', 'Freddie Mac', 'PMMS', '30年固定', 'Affordability', 'Rate Lock-in'],
  },
  {
    indicatorId: 'existing-home-sales',
    title: '中古住宅販売件数',
    country: 'usa',
    category: 'housing',
    summary: '住宅市場の実需を映す指標。賃金だけでなく、住宅ローン金利・住宅価格・在庫・融資条件・既存保有者の住み替え行動が大きく左右する。',
    loadContent: loadMd('usa/existing-home-sales.md'),
    relatedIndicators: ['mortgage-rates', 'housing-starts-permits', 'redfin-case-shiller', 'pending-home-sales'],
    tags: ['中古住宅', 'Existing Home Sales', 'NAR', '住宅ローン金利', '住宅在庫', '住み替え'],
  },
  {
    indicatorId: 'housing-starts-permits',
    title: '住宅着工件数 / 建設許可件数',
    country: 'usa',
    category: 'housing',
    summary: '住宅着工は金利感応度が高く景気回復初期に動きやすい先行指標。建築許可は着工にさらに先行する。金利・雇用・信用環境の総合判断が必要で、GDPには住宅投資を通じて影響。戸建てと集合住宅の区分や四半期平均での把握も重要。',
    loadContent: loadMd('usa/housing-starts-permits.md'),
    relatedIndicators: ['mortgage-rates', 'existing-home-sales', 'redfin-case-shiller', 'bank-lending', 'nahb-hmi'],
    tags: ['住宅着工', 'Housing Starts', '建設許可', 'Building Permits', 'Census Bureau', '先行指標', '住宅投資', 'GDP', '景気循環', '金利', '戸建て', '集合住宅'],
  },
  {
    indicatorId: 'nahb-hmi',
    title: 'NAHB住宅市場指数（HMI）',
    country: 'usa',
    category: 'housing',
    summary: '新築一戸建て市場に対する住宅会社の景況感を示す月次指数。50が強気・弱気の分岐点。金利に敏感だが、建設コスト・労働力・土地不足など供給側要因も影響。サブ指数（販売見通し・来場状況）の先行変化に注目。',
    loadContent: loadMd('usa/nahb-hmi.md'),
    relatedIndicators: ['housing-starts-permits', 'mortgage-rates', 'existing-home-sales', 'new-home-sales'],
    tags: ['NAHB', 'HMI', '住宅市場指数', '景況感', '新築一戸建て', '住宅ローン金利', 'センチメント', '先行指標'],
  },
  {
    indicatorId: 'pending-home-sales',
    title: '中古住宅販売保留数',
    country: 'usa',
    category: 'housing',
    summary: '中古住宅の売買契約成立段階を示す指標。中古住宅販売件数に1〜2か月先行しやすい。住宅ローン金利・住宅価格・所得環境・在庫・購入可能性の影響を強く受ける。',
    loadContent: loadMd('usa/pending-home-sales.md'),
    relatedIndicators: ['existing-home-sales', 'mortgage-rates', 'redfin-case-shiller', 'housing-starts-permits'],
    tags: ['中古住宅販売保留', 'Pending Home Sales', 'NAR', '先行指標', '住宅ローン金利', 'Affordability', '契約'],
  },
  {
    indicatorId: 'redfin-case-shiller',
    title: '住宅価格指数',
    country: 'usa',
    category: 'housing',
    summary: '住宅価格は資産効果を通じて消費に影響。上昇は既存保有者に追い風だが購入予定者には負担増で、家計全体への影響は一様ではない。',
    loadContent: loadMd('usa/redfin-case-shiller.md'),
    relatedIndicators: ['mortgage-rates', 'existing-home-sales', 'housing-starts-permits'],
    tags: ['住宅価格', 'Case-Shiller', 'Redfin', '資産効果', '消費', '住宅市場'],
  },

  // --- マーケット / 中立金利 ---
  {
    indicatorId: 'neutral-rate',
    title: '中立金利',
    country: 'market',
    category: 'economy',
    summary: '景気を過熱させも冷やしもしない金利水準。自然利子率＋期待インフレ率で捉え、金融政策の緩和・引き締め度合いを判断する目安。',
    loadContent: loadMd('market/neutral-rate.md'),
    relatedIndicators: ['policy-rate', 'boj-policy-rate-chart', 'term-premium'],
    tags: ['中立金利', '自然利子率', 'r*', '金融政策', '日銀', 'ECB', 'FRB', '期待インフレ'],
  },

  // --- マーケット / 経常収支 ---
  {
    indicatorId: 'current-account',
    title: '経常収支と財政収支',
    country: 'market',
    category: 'economy',
    summary: '経常収支は海外との財・サービス・所得のやり取りを集約した指標。財政収支との関係（双子の赤字）や為替・金利への影響を確認する。',
    loadContent: loadMd('market/current-account.md'),
    relatedIndicators: ['gdp', 'trade-balance'],
    tags: ['経常収支', 'Current Account', '財政収支', '双子の赤字', 'Twin Deficits', '貿易収支', '所得収支', 'GDP比'],
  },

  // --- マーケット / 潜在成長率 ---
  {
    indicatorId: 'potential-growth',
    title: '潜在成長率',
    country: 'market',
    category: 'economy',
    summary: '労働・資本・TFPに基づく中長期的な供給力の趨勢的成長率。金利耐性や金融引き締めの効き具合を考える土台となる指標。',
    loadContent: loadMd('market/potential-growth.md'),
    relatedIndicators: ['gdp', 'neutral-rate', 'capacity-utilization', 'ism-manufacturing'],
    tags: ['潜在成長率', 'Potential Growth', 'TFP', '全要素生産性', '自然利子率', '供給力', 'CBO', '内閣府', '日銀'],
  },

  // --- マーケット / 貿易収支 ---
  {
    indicatorId: 'trade-balance',
    title: '貿易収支',
    country: 'market',
    category: 'economy',
    summary: '通貨の実需や中長期の外貨需給をみるための基本指標。輸出入の内訳・背景と経常収支全体の構造を合わせて読む。',
    loadContent: loadMd('market/trade-balance.md'),
    relatedIndicators: ['current-account', 'gdp'],
    tags: ['貿易収支', 'Trade Balance', '輸出', '輸入', '経常収支', '為替', '交易条件', '資源価格'],
  },

  // --- マーケット / 中銀バランスシート ---
  {
    indicatorId: 'central-bank-balance-sheet',
    title: '中銀バランスシート',
    country: 'market',
    category: 'policy',
    summary: '中央銀行の総資産の増減で金融緩和・引き締めの規模感を把握する基本指標。QE/QTの進捗や流動性供給量を確認する。',
    loadContent: loadMd('market/central-bank-balance-sheet.md'),
    relatedIndicators: ['policy-rate', 'neutral-rate', 'fundamentals-overview'],
    tags: ['中銀バランスシート', 'Central Bank Balance Sheet', 'QE', 'QT', '量的緩和', '量的引締め', '総資産', 'FRB', 'ECB', 'BOJ', 'SNB'],
  },

  // --- マーケット / 銀行バランスシート ---
  {
    indicatorId: 'bank-balance-sheet',
    title: '銀行バランスシート',
    country: 'market',
    category: 'policy',
    summary: '商業銀行の総資産の推移で民間の信用供給量とリスクテイク姿勢を把握する指標。景気・不動産・企業部門への波及を確認する。',
    loadContent: loadMd('market/bank-balance-sheet.md'),
    relatedIndicators: ['central-bank-balance-sheet', 'policy-rate'],
    tags: ['銀行バランスシート', 'Bank Balance Sheet', '商業銀行', '信用供給', '貸出', '総資産', '民間信用'],
  },

  // --- マーケット / マネタリーベース ---
  {
    indicatorId: 'monetary-base',
    title: 'マネタリーベース',
    country: 'market',
    category: 'policy',
    summary: '中央銀行が直接供給する通貨の総量。金融緩和・引き締めの規模感と流動性供給の状況を把握する基本指標。',
    loadContent: loadMd('market/monetary-base.md'),
    relatedIndicators: ['central-bank-balance-sheet', 'policy-rate', 'neutral-rate'],
    tags: ['マネタリーベース', 'Monetary Base', '日銀当座預金', '日本銀行券', '流動性', 'QE', 'QT', '公開市場操作', 'オペレーション'],
  },

  // --- マーケット / マネーストック ---
  {
    indicatorId: 'money-stock',
    title: 'マネーストック（旧マネーサプライ）',
    country: 'market',
    category: 'policy',
    summary: '金融部門から経済全体に供給されている通貨の総量。M1・M2・M3・広義流動性の定義差と各国の見方を整理。',
    loadContent: loadMd('market/money-stock.md'),
    relatedIndicators: ['monetary-base', 'central-bank-balance-sheet', 'ecb-m3', 'm1-m2'],
    tags: ['マネーストック', 'マネーサプライ', 'Money Stock', 'M1', 'M2', 'M3', 'M4', '広義流動性', '信用', '貸出'],
  },

  // --- マーケット / 雇用・労働市場（総論） ---
  {
    indicatorId: 'employment-labor-market',
    title: '雇用・労働市場の見方',
    country: 'market',
    category: 'employment',
    summary: '雇用者数・労働時間・賃金・生産性を分けて見る枠組み。景気循環との先行・一致・遅行の違い、サービスインフレとの関係、失業率だけでは見誤るリスクを整理。',
    loadContent: loadMd('market/employment-labor-market.md'),
    relatedIndicators: ['nonfarm-payrolls'],
    tags: ['雇用', '労働市場', '賃金', '生産性', 'サービスインフレ', '景気循環', '失業率', 'Conference Board'],
  },

  // --- ユーロ圏 / PPI ---
  {
    indicatorId: 'ecb-ppi',
    title: 'PPI（ユーロ圏・生産者物価指数）',
    country: 'eurozone',
    category: 'inflation',
    summary: 'Eurostatが公表する工業生産者物価指数。工業製品の財価格が対象で、HICP に約5ヶ月先行する。',
    loadContent: loadMd('eurozone/ecb-ppi.md'),
    relatedIndicators: ['ppi', 'cgpi', 'ecb-m3'],
    tags: ['PPI', 'ユーロ圏', 'Eurostat', '生産者物価', 'インフレ', '工業'],
  },

  // --- ユーロ圏 / ドイツPPI ---
  {
    indicatorId: 'germany-ppi',
    title: 'PPI（ドイツ）',
    country: 'eurozone',
    category: 'inflation',
    summary: 'Destatisが公表するドイツの工業生産者物価指数。ユーロ圏PPIより1〜2週間早く発表され、CPI に約5ヶ月先行する。',
    loadContent: loadMd('eurozone/germany-ppi.md'),
    relatedIndicators: ['ecb-ppi', 'ppi', 'cgpi'],
    tags: ['PPI', 'ドイツ', 'Destatis', '生産者物価', 'インフレ', '工業'],
  },

  // --- ユーロ圏 / ECB SPF ---
  {
    indicatorId: 'ecb-spf',
    title: 'ECB SPF インフレ期待（ユーロ圏）',
    country: 'eurozone',
    category: 'inflation',
    summary: 'ECBの専門家予想（SPF）によるインフレ期待。期待インフレが賃金に半年〜9か月先行して波及しやすく、賃金圧力の先行指標として有用。',
    loadContent: loadMd('eurozone/ecb-spf.md'),
    relatedIndicators: ['ecb-ppi', 'germany-ppi'],
    tags: ['ECB', 'SPF', 'インフレ期待', '賃金', 'ユーロ圏', '交渉賃金', 'サービスインフレ'],
  },

  // --- ユーロ圏 / PMI ---
  {
    indicatorId: 'ez-pmi',
    title: 'HCOB PMI（ユーロ圏）',
    country: 'eurozone',
    category: 'economy',
    summary: 'ユーロ圏のコンポジットPMIはGDPの方向感を同時～1四半期先行で捉えやすい。財価格との結び付きはECBも製造業価格系列で示しており最も使いやすい地域の一つ。',
    loadContent: loadMd('eurozone/pmi.md'),
    relatedIndicators: ['ecb-ppi', 'germany-ppi', 'global-manufacturing-pmi'],
    tags: ['PMI', 'HCOB', 'ユーロ圏', '製造業', 'サービス業', '景気', '投入価格', '産出価格'],
  },

  // --- ユーロ圏 / ドイツPMI ---
  {
    indicatorId: 'germany-pmi',
    title: 'HCOB PMI（ドイツ）',
    country: 'eurozone',
    category: 'economy',
    summary: 'ドイツのコンポジットPMIは同四半期の現況確認に強い。製造業比重が高く、財価格・供給制約の把握にはドイツ製造業PMIが特に有用。',
    loadContent: loadMd('eurozone/germany-pmi.md'),
    relatedIndicators: ['ez-pmi', 'ecb-ppi', 'germany-ppi', 'global-manufacturing-pmi'],
    tags: ['PMI', 'HCOB', 'ドイツ', '製造業', 'サービス業', '景気', '投入価格', '産出価格'],
  },

  // --- 英国 / PPI ---
  {
    indicatorId: 'uk-ppi',
    title: '生産者物価指数（PPI・英国）',
    country: 'uk',
    category: 'inflation',
    summary: 'ONSが公表する製造業の出荷価格（Output）と投入価格（Input）。CPI に約4ヶ月先行し、PPI先行型の典型国。',
    loadContent: loadMd('uk/uk-ppi.md'),
    relatedIndicators: ['ecb-ppi', 'germany-ppi', 'ppi', 'cgpi'],
    tags: ['PPI', '英国', 'ONS', '生産者物価', 'インフレ', 'Factory Gate'],
  },

  // --- 英国 / BOE インフレ期待 ---
  {
    indicatorId: 'uk-boe-inflation-attitudes',
    title: 'BOE インフレ期待調査（英国）',
    country: 'uk',
    category: 'inflation',
    summary: 'BoEの家計インフレ期待調査。ユーロ圏ほど賃金との先行関係は安定せず、労働需給や最低賃金改定の影響も大きい。短期の期待インフレが実務上参考になりやすい。',
    loadContent: loadMd('uk/uk-boe-inflation-attitudes.md'),
    relatedIndicators: ['uk-ppi'],
    tags: ['BOE', 'インフレ期待', '賃金', '英国', 'サービスCPI', 'ONS'],
  },

  // --- 英国 / PMI ---
  {
    indicatorId: 'uk-pmi',
    title: 'S&P Global PMI（英国）',
    country: 'uk',
    category: 'economy',
    summary: 'サービスPMIとGDPの結び付きが強く、コンポジットPMIも高い整合性を示す。財価格は製造業の投入・産出価格で確認する。',
    loadContent: loadMd('uk/pmi.md'),
    relatedIndicators: ['uk-ppi', 'global-manufacturing-pmi'],
    tags: ['PMI', 'S&P Global', '英国', '製造業', 'サービス業', '景気', '投入価格', '産出価格'],
  },

  // --- カナダ / IPPI ---
  {
    indicatorId: 'ippi',
    title: 'IPPI（カナダ・工業製品価格指数）',
    country: 'canada',
    category: 'inflation',
    summary: 'Statistics Canadaが公表する製造業の産出価格指数。CPI に約7ヶ月先行し、半年先のインフレ圧力を読む補助指標。',
    loadContent: loadMd('canada/ippi.md'),
    relatedIndicators: ['ppi', 'cgpi', 'ecb-ppi', 'uk-ppi'],
    tags: ['IPPI', 'RMPI', 'カナダ', 'Statistics Canada', '生産者物価', 'インフレ', '工業'],
  },

  // --- カナダ / PMI ---
  {
    indicatorId: 'ivey-pmi',
    title: 'Ivey PMI（カナダ）',
    country: 'canada',
    category: 'economy',
    summary: 'カナダ全産業型の景況感指数。月次GDPとの予測力が高く、Prices指数も別建てで存在する。景気全体はIvey、工業・財価格はS&P製造業PMIという使い分けが有効。',
    loadContent: loadMd('canada/pmi.md'),
    relatedIndicators: ['ca-sp-pmi', 'ippi', 'global-manufacturing-pmi'],
    tags: ['PMI', 'Ivey', 'カナダ', '全産業', '景気', '月次GDP'],
  },
  {
    indicatorId: 'sp-pmi',
    title: 'S&P Global PMI（カナダ）',
    country: 'canada',
    category: 'economy',
    summary: 'S&P Globalのカナダ製造業PMI。工業・財価格の把握に有用で、Ivey PMIと組み合わせて使う。',
    loadContent: loadMd('canada/pmi.md'),
    relatedIndicators: ['ivey-pmi', 'ippi', 'global-manufacturing-pmi'],
    tags: ['PMI', 'S&P Global', 'カナダ', '製造業', '景気', '投入価格', '産出価格'],
  },

  // --- 中国 / PPI ---
  {
    indicatorId: 'cn-ppi',
    title: 'PPI（中国・工業生産者物価指数）',
    country: 'china',
    category: 'inflation',
    summary: 'NBSが公表する工業部門の産出・購入価格指数。CPIとの連動は弱く、工業部門の価格圧力を独立に評価する指標。',
    loadContent: loadMd('china/cn-ppi.md'),
    relatedIndicators: ['ecb-ppi', 'ppi', 'cgpi', 'uk-ppi'],
    tags: ['PPI', '中国', 'NBS', '生産者物価', 'インフレ', '工業'],
  },

  // --- 中国 / PMI ---
  {
    indicatorId: 'cn-pmi',
    title: 'NBS PMI（中国）',
    country: 'china',
    category: 'economy',
    summary: '公式非製造業PMIの方がGDP全体との整合性が高い。製造業PMIは工業・輸出・財循環の把握に使い、コスト上昇と価格転嫁は必ずしも一致しない点に注意。',
    loadContent: loadMd('china/pmi.md'),
    relatedIndicators: ['cn-ppi', 'caixin-pmi', 'global-manufacturing-pmi'],
    tags: ['PMI', 'NBS', '中国', '製造業', '非製造業', 'Caixin', '景気', '投入価格', '産出価格'],
  },

  // --- 中国 / 財新PMI ---
  {
    indicatorId: 'caixin-pmi',
    title: '財新PMI（中国）',
    country: 'china',
    category: 'economy',
    summary: '民間・輸出関連企業を含む中国製造業の景況感指標。ISM製造業景況指数に1〜2か月程度先行しやすい補助指標として、世界製造業サイクルの方向感把握に有用。',
    loadContent: loadMd('china/caixin-pmi.md'),
    relatedIndicators: ['ism-manufacturing', 'cn-pmi', 'global-manufacturing-pmi', 'cn-electronics-stock', 'taiwan-export-orders'],
    tags: ['PMI', 'Caixin', '中国', '製造業', 'サービス業', 'ISM', '景気', '先行指標', '世界製造業サイクル'],
  },

  // --- 中国 / 電気機器在庫 ---
  {
    indicatorId: 'cn-electronics-stock',
    title: '電気機器在庫（中国）',
    country: 'china',
    category: 'economy',
    summary: 'NBS公表の電気機械在庫増減率。SOX→台湾輸出受注→ISM→中国在庫の波及の流れで最も遅行し、半導体・電子機器サイクルの実体波及を確認する後追い指標。',
    loadContent: loadMd('china/cn-electronics-stock.md'),
    relatedIndicators: ['taiwan-export-orders', 'ism-manufacturing', 'semiconductor-sales', 'cn-pmi'],
    tags: ['中国', '在庫', '電気機器', 'NBS', 'SOX', '半導体', 'エレクトロニクス循環', '遅行指標'],
  },

  // --- スイス / PPI ---
  {
    indicatorId: 'ch-ppi',
    title: 'PPI（スイス・生産者輸入物価指数）',
    country: 'switzerland',
    category: 'inflation',
    summary: 'FSOが公表する生産者価格＋輸入価格の統合指数。core2 CPIに約8ヶ月先行し、基調インフレの方向感を先読みする材料。',
    loadContent: loadMd('switzerland/ch-ppi.md'),
    relatedIndicators: ['ecb-ppi', 'ppi', 'cgpi', 'uk-ppi'],
    tags: ['PPI', 'スイス', 'FSO', 'BFS', '生産者物価', '輸入物価', 'インフレ', 'CHF'],
  },

  // --- スイス / PMI ---
  {
    indicatorId: 'ch-pmi',
    title: 'PMI（スイス）',
    country: 'switzerland',
    category: 'economy',
    summary: 'procure.ch/UBSのPMI。製造業PMIとGDP前年比の相関が高く同四半期の現況確認に有効。財価格は製造業、国内サービスコストはサービスPMIで使い分ける。',
    loadContent: loadMd('switzerland/ch-pmi.md'),
    relatedIndicators: ['ch-ppi', 'global-manufacturing-pmi'],
    tags: ['PMI', 'procure.ch', 'UBS', 'スイス', '製造業', 'サービス業', '景気', '投入価格', '産出価格'],
  },

  // --- ニュージーランド / PPI ---
  {
    indicatorId: 'nz-ppi',
    title: 'PPI（ニュージーランド・生産者物価指数）',
    country: 'newzealand',
    category: 'inflation',
    summary: 'Stats NZが公表するOutput/Input型の四半期PPI。Output PPIの前年比がCPIに約1四半期先行し、インフレ基調の先行確認に有用。',
    loadContent: loadMd('newzealand/nz-ppi.md'),
    relatedIndicators: ['au-ppi', 'ppi', 'uk-ppi', 'cgpi'],
    tags: ['PPI', 'ニュージーランド', 'Stats NZ', '生産者物価', 'インフレ', 'Output', 'Input', '四半期'],
  },

  // --- ニュージーランド / PMI ---
  {
    indicatorId: 'nz-pmi',
    title: 'PMI / PSI / PCI（ニュージーランド）',
    country: 'newzealand',
    category: 'economy',
    summary: 'BusinessNZのPMI・PSI・PCI。GDP加重の総合PCIが最もGDPと整合的。財価格はPMI、内需・サービス価格はPSIという分担が適切。',
    loadContent: loadMd('newzealand/pmi.md'),
    relatedIndicators: ['nz-ppi', 'global-manufacturing-pmi'],
    tags: ['PMI', 'PSI', 'PCI', 'BusinessNZ', 'ニュージーランド', '製造業', 'サービス業', '景気'],
  },

  // --- オーストラリア / PPI ---
  {
    indicatorId: 'au-ppi',
    title: 'PPI（オーストラリア・生産者物価指数）',
    country: 'australia',
    category: 'inflation',
    summary: 'ABSが公表する四半期ベースの生産者物価指数。財＋サービスの広いカバレッジを持ち、CPIとラグ0で同期的に動く。',
    loadContent: loadMd('australia/au-ppi.md'),
    relatedIndicators: ['ppi', 'cgpi', 'ecb-ppi', 'uk-ppi', 'cn-ppi'],
    tags: ['PPI', 'オーストラリア', 'ABS', '生産者物価', 'インフレ', 'Final Demand', '四半期'],
  },

  // --- オーストラリア / PMI ---
  {
    indicatorId: 'au-pmi',
    title: 'S&P Global PMI（オーストラリア）',
    country: 'australia',
    category: 'economy',
    summary: 'Judo Bank PMI。総合・サービスPMIが同四半期GDPとの整合性が高く、製造業PMIは一部で1四半期先行する。サービス投入価格は国内インフレ圧力も含む。',
    loadContent: loadMd('australia/pmi.md'),
    relatedIndicators: ['au-ppi', 'global-manufacturing-pmi'],
    tags: ['PMI', 'S&P Global', 'Judo Bank', 'オーストラリア', '製造業', 'サービス業', '景気', '投入価格', '産出価格'],
  },

  // --- オーストラリア / 消費 ---
  {
    indicatorId: 'household-saving-ratio',
    title: '家計貯蓄率（オーストラリア）',
    country: 'australia',
    category: 'consumer',
    summary: '可処分所得のうち消費に回さず残した割合。フロー（貯蓄率）とストック（貯蓄残高）の混同に注意。上昇は消費抑制、低下は支出姿勢の強まりを示唆。',
    loadContent: loadMd('australia/household-saving-ratio.md'),
    relatedIndicators: ['disposable-personal-income'],
    tags: ['貯蓄率', 'Household Saving Ratio', 'ABS', '可処分所得', '消費', '家計'],
  },
  {
    indicatorId: 'disposable-personal-income',
    title: '可処分所得（オーストラリア）',
    country: 'australia',
    category: 'consumer',
    summary: '家計が消費か貯蓄に配分できる所得。名目ではなく実質可処分所得で購買力の変化を見ることが重要。',
    loadContent: loadMd('australia/disposable-personal-income.md'),
    relatedIndicators: ['household-saving-ratio'],
    tags: ['可処分所得', 'Disposable Income', 'ABS', '実質所得', '購買力', '消費'],
  },

  // --- ユーロ圏 / ECB M3 ---
  {
    indicatorId: 'ecb-m3',
    title: 'ユーロ圏M3マネーサプライ',
    country: 'eurozone',
    category: 'policy',
    summary: 'ECBが重視する広義マネー指標。M3と民間向け貸出を並べて信用環境や政策波及の状況を確認する。',
    loadContent: loadMd('eurozone/ecb-m3.md'),
    relatedIndicators: ['money-stock', 'monetary-base', 'central-bank-balance-sheet'],
    tags: ['M3', 'ECB', 'ユーロ圏', 'マネーサプライ', '信用', '貸出', 'Monetary developments'],
  },

  // --- 中国 / M1・M2 ---
  {
    indicatorId: 'm1-m2',
    title: '中国M1・M2（貨幣供応量）',
    country: 'china',
    category: 'policy',
    summary: 'M2で信用総量、M1で取引性・流動性の強弱を確認。2025年1月のM1定義改訂に注意。',
    loadContent: loadMd('china/m1-m2.md'),
    relatedIndicators: ['money-stock', 'monetary-base', 'central-bank-balance-sheet'],
    tags: ['M1', 'M2', '中国', '貨幣供応量', 'PBOC', '人民銀行', '信用', '流動性', '統計改訂'],
  },
]

// --- ルックアップ用マップ ---
export const HANDBOOK_MAP = new Map<string, HandbookEntry>(
  HANDBOOK_ENTRIES.map((entry) => [entry.indicatorId, entry])
)

// --- カテゴリ名マッピング ---
export const HANDBOOK_CATEGORY_LABELS: Record<string, string> = {
  policy: '金融政策',
  economy: '経済',
  consumer: '消費',
  employment: '雇用',
  inflation: '物価',
  housing: '住宅',
  equities: '株式',
  forex: '為替',
  commodities: 'コモディティ',
  energy: 'エネルギー',
  cot: 'CFTCポジション',
  flow: 'フロー',
  rebalance: 'リバランス',
  anomaly: 'アノマリー',
  options: 'オプション',
  correlation: '相関関係',
}

export const HANDBOOK_COUNTRY_LABELS: Record<string, string> = {
  usa: 'アメリカ',
  japan: '日本',
  eurozone: 'ユーロ圏',
  uk: 'イギリス',
  china: '中国',
  australia: 'オーストラリア',
  newzealand: 'ニュージーランド',
  canada: 'カナダ',
  switzerland: 'スイス',
  global: 'グローバル',
  market: 'マーケット',
}
