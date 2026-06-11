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
// Vite の import.meta.glob を eager 指定で、全 md をビルド時にバンドルへ同梱。
// クリック時に追加のフェッチが発生せず、ヘルプパネルが即時表示される。
const mdModules = import.meta.glob<string>('./indicators/**/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
})

function loadMd(path: string): () => Promise<string> {
  const key = `./indicators/${path}`
  const content = mdModules[key]
  if (content === undefined) {
    return () => Promise.resolve(`> コンテンツ準備中: ${path}`)
  }
  return () => Promise.resolve(content)
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
  {
    indicatorId: 'sofr-volatility',
    title: 'SOFR / ボラティリティ',
    country: 'usa',
    category: 'policy',
    summary: 'NY Fed公表の米国債担保付翌日物レポ金利と、その日次変化に基づく20日ローリング標準偏差。米ドル短期資金市場の調達コストと変動の荒さを把握する指標。',
    loadContent: loadMd('usa/sofr-volatility.md'),
    relatedIndicators: ['policy-rate', 'on-rrp', 'reserve-balances', 'fed-watch'],
    tags: ['SOFR', 'NY Fed', 'レポ', '翌日物', '短期金利', 'ボラティリティ', '20日標準偏差', 'LIBOR代替', 'ARRC', 'SOFR Index', '担保付調達金利'],
  },
  {
    indicatorId: 'frb-total-assets',
    title: 'FRB総資産',
    country: 'usa',
    category: 'policy',
    summary: 'FRB週次統計H.4.1の連結総資産（WALCL）。QE/QT・流動性供給・金融ストレス対応を映すバランスシート指標。準備預金・TGA・ON RRPと併せて読む。',
    loadContent: loadMd('usa/frb-total-assets.md'),
    relatedIndicators: ['reserve-balances', 'tga', 'on-rrp', 'policy-rate', 'sofr-volatility'],
    tags: ['FRB', 'バランスシート', 'WALCL', 'H.4.1', 'QE', 'QT', '量的緩和', '量的引き締め', '準備預金', 'TGA', 'ON RRP', '米国債', 'MBS', '中央銀行'],
  },
  {
    indicatorId: 'reserve-balances',
    title: '準備預金残高',
    country: 'usa',
    category: 'policy',
    summary: '銀行がFRBに保有する口座残高。米ドル流動性とample reserves枠組みの中核。FRB総資産・TGA・ON RRPと組み合わせて短期金利の安定性を読む。',
    loadContent: loadMd('usa/reserve-balances.md'),
    relatedIndicators: ['frb-total-assets', 'tga', 'on-rrp', 'sofr-volatility', 'policy-rate'],
    tags: ['準備預金', 'Reserve Balances', 'WRESBAL', 'H.4.1', 'IORB', 'ample reserves', '米ドル流動性', '銀行間決済', 'TGA', 'ON RRP', 'SOFR', 'FF金利'],
  },
  {
    indicatorId: 'tga',
    title: 'TGA（財務省一般勘定）',
    country: 'usa',
    category: 'policy',
    summary: '米財務省がFRBに保有する運転資金口座。税収・国債発行・政府支出で増減し、準備預金との入れ替わりでドル流動性に直接影響する。',
    loadContent: loadMd('usa/tga.md'),
    relatedIndicators: ['reserve-balances', 'frb-total-assets', 'on-rrp', 'sofr-volatility', 'policy-rate'],
    tags: ['TGA', 'Treasury General Account', '財務省一般勘定', '米財務省', 'H.4.1', 'Daily Treasury Statement', '準備預金', 'ON RRP', '債務上限', '国債発行', '税収', 'SOFR', 'レポ金利'],
  },
  {
    indicatorId: 'on-rrp',
    title: 'ON RRP（Overnight Reverse Repo）',
    country: 'usa',
    category: 'policy',
    summary: 'NY Fed Open Market Deskが日次で実施する翌日物リバースレポ。MMFなど非銀行が利用し、ON RRP金利は短期金利の下限として機能する。残高は資金吸収量を示す。',
    loadContent: loadMd('usa/on-rrp.md'),
    relatedIndicators: ['tga', 'reserve-balances', 'frb-total-assets', 'sofr-volatility', 'policy-rate'],
    tags: ['ON RRP', 'Reverse Repo', '翌日物リバースレポ', 'NY Fed', 'MMF', 'マネー・マーケット・ファンド', '短期金利', 'フロア', 'IORB', 'SOMA', 'SOFR', 'T-bill', '余剰流動性'],
  },
  {
    indicatorId: 'federal-budget',
    title: '連邦財政収支',
    country: 'usa',
    category: 'policy',
    summary: '米財務省MTS公表の月次連邦財政収支（歳入−歳出）。FY累計と前年同月比で確認し、国債発行・TGA・米債需給と組み合わせて読む。',
    loadContent: loadMd('usa/federal-budget.md'),
    relatedIndicators: ['tga', 'cbo-projections', 'us-treasury-yields', 'frb-total-assets'],
    tags: ['連邦財政収支', 'Federal Budget Balance', 'MTS', 'Monthly Treasury Statement', '米財務省', 'Bureau of the Fiscal Service', '歳入', '歳出', '財政赤字', '財政黒字', '会計年度', 'FYTD', 'CBO', '個人所得税', '法人税', '関税', '社会保障', 'メディケア', '利払い費'],
  },
  {
    indicatorId: 'cbo-projections',
    title: 'CBO財政見通し',
    country: 'usa',
    category: 'policy',
    summary: '議会予算局による現行法ベースの中期財政見通し。歳入・歳出・赤字・債務残高の10年見通しを、GDP比と純利払い費の動向を中心に確認する。',
    loadContent: loadMd('usa/cbo-projections.md'),
    relatedIndicators: ['federal-budget', 'tga', 'term-premium', 'us-treasury-yields'],
    tags: ['CBO', 'Congressional Budget Office', '議会予算局', '財政見通し', 'Budget Projections', 'ベースライン', '会計年度', '財政赤字', '債務残高', '公衆保有債務', 'GDP比', '純利払い費', 'プライマリーバランス', '社会保障', 'メディケア', 'タームプレミアム'],
  },
  {
    indicatorId: 'cre-loan-delinquency',
    title: 'CREローン延滞率',
    country: 'usa',
    category: 'policy',
    summary: '米商業銀行の商業用不動産ローン延滞率（全行・上位100行・その他）。CRE信用ストレスの遅行指標で、チャージオフ率・銀行貸出態度と組み合わせて読む。',
    loadContent: loadMd('usa/cre-loan-delinquency.md'),
    relatedIndicators: ['bank-lending', 'oas', 'nfci', 'mortgage-rates'],
    tags: ['CRE', '商業用不動産', 'Commercial Real Estate', 'ローン延滞率', 'Delinquency', '銀行貸出', 'チャージオフ', '信用ストレス', '上位100行', '地域銀行', 'FRB', 'FRED', 'CMBS', 'オフィス不動産'],
  },
  {
    indicatorId: 'quarterly-refunding',
    title: 'Quarterly Refunding（米財務省）',
    country: 'usa',
    category: 'policy',
    summary: '米財務省が四半期ごとに公表する米国債発行・借換計画。借入見込み・年限構成・TGA想定残高・TBAC提言から、長期金利・タームプレミアム・流動性を読む。',
    loadContent: loadMd('usa/quarterly-refunding.md'),
    relatedIndicators: ['federal-budget', 'cbo-projections', 'tga', 'term-premium', 'us-treasury-yields'],
    tags: ['Quarterly Refunding', '四半期定例入札', '米財務省', 'U.S. Treasury', '国債発行', '借換', 'TBAC', 'Primary Dealer', 'T-Bill', 'クーポン債', 'TIPS', 'FRN', 'Buyback', 'TGA', 'タームプレミアム', 'デュレーション', '入札サイズ', 'Financing Estimates'],
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
    indicatorId: 'nairu',
    title: 'NAIRU（非循環的失業率 / 自然失業率）',
    country: 'usa',
    category: 'employment',
    summary: 'CBO推計の非循環的失業率（FRED NROU）。インフレを加速させない労働市場の均衡水準で、実際の失業率との差（失業率ギャップ）から労働市場の過熱・スラックを判断する基準線。',
    loadContent: loadMd('usa/nairu.md'),
    relatedIndicators: ['unemployment', 'sahm-rule', 'labor-force-participation', 'average-hourly-earnings', 'atlanta-fed-wage'],
    tags: ['NAIRU', '自然失業率', '非循環的失業率', 'Noncyclical Rate of Unemployment', 'NROU', 'CBO', '失業率ギャップ', 'フィリップス曲線', 'インフレ', '労働市場', 'スラック', 'FRED'],
  },
  {
    indicatorId: 'unemployment-by-reason',
    title: '失業率内訳（理由別）',
    country: 'usa',
    category: 'employment',
    summary: 'BLS Table A-11の失業理由別構成（失職者・自発的離職・再参入・新規参入）。失業率上昇が失職者主導か供給増加主導かを切り分ける。',
    loadContent: loadMd('usa/unemployment-by-reason.md'),
    relatedIndicators: ['unemployment', 'sahm-rule', 'nonfarm-payrolls', 'initial-claims', 'labor-force-participation'],
    tags: ['失業率内訳', 'Reason for Unemployment', 'Table A-11', 'BLS', 'CPS', '失職者', '一時レイオフ', 'Job losers', 'Job leavers', '自発的離職', 'Reentrants', '再参入者', 'New entrants', '新規参入者', '景気後退'],
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
    indicatorId: 'workers-by-place-of-birth',
    title: '出生地別の労働力人口・雇用者数（Native / Foreign Born）',
    country: 'usa',
    category: 'employment',
    summary: 'CPS（家計調査）の Table A-7 に基づく米国生まれ／外国生まれ別の労働力人口と雇用者数。移民政策、労働供給制約、賃金圧力が市場テーマになる局面で補助指標として有効。',
    loadContent: loadMd('usa/workers-by-place-of-birth.md'),
    relatedIndicators: ['nonfarm-payrolls', 'unemployment', 'labor-force-participation', 'average-hourly-earnings', 'fullpart-time'],
    tags: ['出生地別', 'Native Born', 'Foreign Born', '米国生まれ', '外国生まれ', '労働力人口', '雇用者数', '移民', '労働供給', 'BLS', 'CPS', 'Table A-7'],
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
    indicatorId: 'used-car-prices',
    title: '中古車価格（CPI 中古車 / Manheim 中古車）',
    country: 'usa',
    category: 'inflation',
    summary: 'BLS公表のCPI中古車（CUSR0000SETA02）と、Cox Automotive / Manheimの卸売中古車価格指数（UVVI）を比較。Manheimは卸売段階の先行指標としてCPI中古車の方向感を読む。',
    loadContent: loadMd('usa/used-car-prices.md'),
    relatedIndicators: ['cpi', 'cpi-categories', 'pce-deflator'],
    tags: ['中古車', 'Used Cars', 'CPI', 'Manheim', 'Cox Automotive', 'UVVI', '卸売', '小売', 'BLS', 'コア財', 'コアCPI', '先行指標', 'リース戻り', '新車供給', 'CUSR0000SETA02', 'FRED'],
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

  // --- Japan / 金融政策（日銀当座預金） ---
  {
    indicatorId: 'boj-current-account-balance',
    title: '日銀当座預金と資金過不足',
    country: 'japan',
    category: 'policy',
    summary: '民間金融機関が日銀に保有する決済用預金。銀行券要因と財政等要因による資金過不足は短期金利の需給圧力を示す。季節性が強いが制度変更で崩れることもある。',
    loadContent: loadMd('japan/boj-current-account-balance.md'),
    relatedIndicators: ['boj-policy-rate-chart', 'boj-meeting-expectations', 'ois-curve-chart'],
    tags: ['日銀当座預金', '資金過不足', '銀行券要因', '財政等要因', '短期金利', 'コールレート', '日本銀行', '金融調節'],
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
    indicatorId: 'cpi-categories',
    title: '全国CPI 10大費目（日本）',
    country: 'japan',
    category: 'inflation',
    summary: '食料・エネルギーの家計影響と輸入物価からCPIへの波及ラグ。エネルギー5項目の構成、食料価格の国内供給要因、政策要因による振れを整理。',
    loadContent: loadMd('japan/cpi-categories.md'),
    relatedIndicators: ['national-cpi', 'tokyo-cpi', 'cgpi'],
    tags: ['CPI', '食料', 'エネルギー', '10大費目', '物価', '総務省', '輸入物価', '為替', '波及ラグ', '電気代', 'ガソリン'],
  },

  {
    indicatorId: 'tokyo-cpi',
    title: '東京都区部CPI',
    country: 'japan',
    category: 'inflation',
    summary: '全国CPIより先に公表される速報的な物価指標。総合・コア・コアコアのいずれでも全国CPIと高い連動性を持ち、物価モメンタムの強弱を把握する先行材料として重要。',
    loadContent: loadMd('japan/tokyo-cpi.md'),
    relatedIndicators: ['national-cpi', 'cgpi', 'boj-policy-rate-chart'],
    tags: ['東京CPI', 'CPI', '物価', '総務省', 'インフレ', 'コアCPI', 'コアコアCPI', '先行指標'],
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

  {
    indicatorId: 'import-export-price',
    title: '輸入・輸出物価指数（日本）',
    country: 'japan',
    category: 'inflation',
    summary: '輸入物価から食品・エネルギーCPIへの波及経路とラグ。食品は12〜13か月、エネルギーは品目別に3〜5か月のラグ。為替・国際市況・政策要因の切り分けが重要。',
    loadContent: loadMd('japan/import-export-price.md'),
    relatedIndicators: ['national-cpi', 'cpi-categories', 'cgpi', 'terms-of-trade'],
    tags: ['輸入物価', '輸出物価', '為替', '円安', '食品', 'エネルギー', '原油', 'LNG', '価格転嫁', '日本銀行', 'CPI'],
  },

  {
    indicatorId: 'sppi',
    title: '企業向けサービス価格指数（SPPI / CSPI）',
    country: 'japan',
    category: 'inflation',
    summary: '日本銀行が公表する企業間サービス価格指数。7大類別146品目で構成され、財価格では捉えにくいサービスコスト圧力・価格転嫁の動きを補足する。',
    loadContent: loadMd('japan/sppi.md'),
    relatedIndicators: ['cgpi', 'national-cpi', 'import-export-price'],
    tags: ['SPPI', 'CSPI', 'サービス価格', '企業向け', '日本銀行', '物価', '価格転嫁', '運輸', '情報通信'],
  },

  {
    indicatorId: 'pos-uvpi',
    title: 'POS-UVPI（消費者購買単価指数）',
    country: 'japan',
    category: 'inflation',
    summary: '全国約6000店舗のPOSデータによる週次購買単価指数。容量変化・商品入替を反映し、日用品・加工食品の価格動向を月次CPI より早く確認できる。',
    loadContent: loadMd('japan/pos-uvpi.md'),
    relatedIndicators: ['national-cpi', 'cpi-categories', 'cgpi'],
    tags: ['POS-UVPI', '購買単価', 'POSデータ', '一橋大学', '食料品', '日用品', '実質値上げ', '週次'],
  },

  {
    indicatorId: 'terms-of-trade',
    title: '交易条件',
    country: 'japan',
    category: 'inflation',
    summary: '輸出物価÷輸入物価で測る価格交換比率。資源価格・円相場・輸出価格の主因を分解し、企業収益・実質所得・貿易収支への波及を読む。',
    loadContent: loadMd('japan/terms-of-trade.md'),
    relatedIndicators: ['import-export-price', 'cgpi', 'national-cpi', 'japan-fundamentals-yen'],
    tags: ['交易条件', 'Terms of Trade', '輸出物価', '輸入物価', 'FOB', 'CIF', '日本銀行', '資源価格', '原油', 'LNG', '円安', '為替', '実質所得', '価格転嫁', '貿易収支'],
  },

  // --- Japan / 物価（GDPギャップ） ---
  {
    indicatorId: 'gdp-gap',
    title: '日本GDPギャップ',
    country: 'japan',
    category: 'inflation',
    summary: '実際のGDPと潜在GDPの乖離を示す需給バランス指標。プラスは需要超過、マイナスは需要不足。物価・雇用との関係が深く、日銀の政策判断材料としても重要。',
    loadContent: loadMd('japan/gdp-gap.md'),
    relatedIndicators: ['quarterly-gdp', 'potential-growth', 'national-cpi', 'boj-policy-rate-chart'],
    tags: ['GDPギャップ', '需給ギャップ', '潜在GDP', '内閣府', '日本銀行', '物価', '雇用', 'フィリップス曲線'],
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

  // --- Japan / 経済（日銀短観） ---
  {
    indicatorId: 'boj-tankan',
    title: '日銀短観',
    country: 'japan',
    category: 'economy',
    summary: '日本銀行が四半期ごとに実施する企業アンケート。業況判断DI・設備判断DI・価格判断DI・設備投資計画など、景況感から事業計画まで幅広く把握できる。',
    loadContent: loadMd('japan/boj-tankan.md'),
    relatedIndicators: ['quarterly-gdp', 'pmi', 'cgpi', 'boj-policy-rate-chart'],
    tags: ['短観', '日銀', 'BOJ', 'Tankan', 'DI', '業況判断', '設備投資', '販売価格', '仕入価格', '雇用', '景況感', '四半期'],
  },

  // --- Japan / 経済（鉱工業生産） ---
  {
    indicatorId: 'iip',
    title: '鉱工業生産指数',
    country: 'japan',
    category: 'economy',
    summary: '鉱業・製造工業の生産活動を指数化した指標。関連産業への波及が大きく、GDP成長率と連動しやすいため、景気の強弱を判断する基礎指標として使われる。',
    loadContent: loadMd('japan/iip.md'),
    relatedIndicators: ['japan-capacity-utilization', 'boj-tankan', 'pmi', 'quarterly-gdp'],
    tags: ['鉱工業生産', 'IIP', '製造業', '景気', 'GDP', '在庫循環', '経済産業省'],
  },

  // --- Japan / 経済（稼働率指数） ---
  {
    indicatorId: 'japan-capacity-utilization',
    title: '鉱工業生産稼働率指数',
    country: 'japan',
    category: 'economy',
    summary: '製造業の設備がどの程度使われているかを示す指標。稼働率上昇は需給逼迫や設備投資拡大の方向性を示す材料として注目される。',
    loadContent: loadMd('japan/capacity-utilization.md'),
    relatedIndicators: ['iip', 'boj-tankan', 'pmi', 'quarterly-gdp'],
    tags: ['稼働率', '設備稼働率', '製造業', '設備投資', '需給', 'インフレ', '経済産業省'],
  },

  // --- Japan / 経済（機械受注） ---
  {
    indicatorId: 'machinery-orders',
    title: '機械受注',
    country: 'japan',
    category: 'economy',
    summary: '船舶・電力を除く民需が設備投資の先行指標。単月のブレが大きいため3か月移動平均や四半期ベースで基調を確認する。四半期見通しの達成率も投資マインドの把握に有効。',
    loadContent: loadMd('japan/machinery-orders.md'),
    relatedIndicators: ['boj-tankan', 'iip', 'japan-capacity-utilization', 'quarterly-gdp'],
    tags: ['機械受注', '設備投資', '民需', '船舶電力除く', '内閣府', 'ESRI', '先行指標', '達成率'],
  },

  // --- Japan / 経済（工作機械受注） ---
  {
    indicatorId: 'machine-tool-orders',
    title: '工作機械受注',
    country: 'japan',
    category: 'economy',
    summary: '企業の設備投資意欲を反映する代表的な指標。グローバル製造業PMIと強い正の相関を持ち、TOPIX予想EPSの前年比に2～4か月先行する傾向がある。',
    loadContent: loadMd('japan/machine-tool-orders.md'),
    relatedIndicators: ['machinery-orders', 'boj-tankan', 'global-manufacturing-pmi', 'topix_valuation_eps'],
    tags: ['工作機械受注', '設備投資', '製造業', 'PMI', 'EPS', '日本工作機械工業会', '先行指標'],
  },

  // --- Japan / 経済（貸出動向） ---
  {
    indicatorId: 'boj-lending',
    title: '日本貸出動向（前年比）',
    country: 'japan',
    category: 'economy',
    summary: '日銀「貸出・預金動向」の月次平残ベース貸出残高前年比。信用循環を捉える指標で、前向き投資需要か防衛的資金需要かを設備投資・短観・倒産と併せて判断する。',
    loadContent: loadMd('japan/boj-lending.md'),
    relatedIndicators: ['boj-tankan', 'machinery-orders', 'boj-policy-rate-chart', 'quarterly-gdp'],
    tags: ['貸出', '貸出動向', '貸出・預金動向', '日本銀行', '平残', '銀行貸出', '都市銀行', '地方銀行', '信用金庫', '信用循環', '資金繰り', '設備投資', '銀行株', '正常化観測'],
  },

  // --- Japan / 消費者（景気ウォッチャー調査） ---
  {
    indicatorId: 'economy-watcher',
    title: '景気ウォッチャー調査',
    country: 'japan',
    category: 'consumer',
    summary: '内閣府が毎月実施する「街角景気」のアンケート調査。現状判断DIと先行き判断DIから、家計・企業・雇用の現場感覚を月次で早期に把握できる。',
    loadContent: loadMd('japan/economy-watcher.md'),
    relatedIndicators: ['quarterly-gdp', 'boj-tankan', 'pmi', 'national-cpi'],
    tags: ['景気ウォッチャー', '内閣府', 'DI', '街角景気', '現状判断', '先行き判断', '家計', '雇用', '景況感'],
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
  {
    indicatorId: 'crack-spread',
    title: 'クラックスプレッド（WTIベース）',
    country: 'market',
    category: 'energy',
    summary: 'RBOBガソリン・ULSDとWTI原油の差。製油所の粗マージン指標。3:2:1クラックを総合採算、RBOB主導／ULSD主導の内訳で需給を切り分け。Brentベースとの違いと精製業の方向感を読む。',
    loadContent: loadMd('market/crack-spread.md'),
    relatedIndicators: ['cot-crude-oil', 'weekly-crude-oil-inventories'],
    tags: ['クラックスプレッド', 'Crack Spread', 'RBOB', 'ULSD', '3:2:1', '製油所', '精製マージン', 'WTI', 'Brent', 'ガソリン', 'ディーゼル', '暖房油', '中間留分', 'CME', 'EIA', '製品需給', 'エネルギー'],
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
  {
    indicatorId: 'noaa-hdd-cdd',
    title: 'HDD/CDD & 気温見通し',
    country: 'market',
    category: 'energy',
    summary: 'NOAA CPC公表のHDD（暖房度日）/CDD（冷房度日）と6–10日・8–14日気温見通し。基準65°Fで計算される気温由来エネルギー需要指標。天然ガス需要・冬の寒気・夏の熱波・地域別需要構造を読む。',
    loadContent: loadMd('market/noaa-hdd-cdd.md'),
    relatedIndicators: ['cot-natural-gas', 'roni'],
    tags: ['HDD', 'CDD', '暖房度日', '冷房度日', 'Heating Degree Days', 'Cooling Degree Days', 'NOAA', 'CPC', 'Climate Prediction Center', '気温見通し', '6-10日', '8-14日', 'NDFD', '天然ガス', 'Natural Gas', '暖房需要', '冷房需要', '寒波', '熱波', 'East North Central', 'Northeast', 'Mid-Atlantic', 'CONUS'],
  },
  {
    indicatorId: 'roni',
    title: 'RONI（Relative Oceanic Niño Index）',
    country: 'market',
    category: 'energy',
    summary: 'NOAA CPCが2026年2月から公式採用するENSO監視指数。Niño 3.4の海面水温偏差から熱帯平均（20°N〜20°S）の偏差を差し引いた相対指数の3か月移動平均。±0.5℃でエルニーニョ／ラニーニャ水準を判定。',
    loadContent: loadMd('market/roni.md'),
    relatedIndicators: ['noaa-hdd-cdd', 'cot-natural-gas'],
    tags: ['RONI', 'Relative Oceanic Niño Index', 'ONI', 'ENSO', 'エルニーニョ', 'ラニーニャ', 'NOAA', 'CPC', 'NCEP', 'Niño 3.4', '海面水温', 'SST', '熱帯太平洋', '気候レジーム', 'ハリケーン', '農産物', '天然ガス', 'storm track', 'ジェット気流'],
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
    relatedIndicators: ['flow-knowledge', 'rebalance', 'cftc-positioning', 'summer-market-reaction'],
    tags: ['アノマリー', 'シーズナリティ', '季節性', '月末月初', 'Sell in May', 'FOMC', 'ゴトー日', 'サンタクロースラリー'],
  },
  {
    indicatorId: 'summer-market-reaction',
    title: '夏相場における価格反応とヘッドライン解釈',
    country: 'market',
    category: 'anomaly',
    summary: '7〜8月は参加者減で流動性が薄く、材料に対して価格が素直に反応しないことがある。ヘッドライン内容より「価格が重要水準を抜けるか／守るか／全戻しするか」と上位足のトレンドを優先する実務指針。',
    loadContent: loadMd('market/summer-market-reaction.md'),
    relatedIndicators: ['anomaly-guide', 'rebalance', 'flow-knowledge', 'autumn-political-risk'],
    tags: ['夏相場', 'サマーラリー', '7月', '8月', 'Sell in May', '低流動性', '薄商い', 'ヘッドライン', 'ヘッドライン解釈', '価格反応', '初動', '全戻し', '重要水平線', '上位足トレンド', 'EMA', '逆張り', '押し目', '戻り売り', 'ストップ狩り', 'リスク管理'],
  },
  {
    indicatorId: 'autumn-political-risk',
    title: '秋の政治リスクと相場の見方',
    country: 'market',
    category: 'anomaly',
    summary: '「秋＝政治不安」ではなく「秋＝議会休会明けで政治日程が密集し、政策・予算・選挙・外交イベントが表面化しやすい時期」と捉える。米予算・債務上限、欧州財政、日本国会、中国政策会議、地政学、OPECなど波及経路を持つ材料を選別する実務指針。',
    loadContent: loadMd('market/autumn-political-risk.md'),
    relatedIndicators: ['anomaly-guide', 'summer-market-reaction', 'year-end-central-banks', 'rebalance', 'flow-knowledge'],
    tags: ['秋相場', '9月', '10月', '11月', '政治リスク', '政治日程', '議会再開', '予算審議', '政府閉鎖', 'CR', 'オムニバス', '債務上限', '選挙', '内閣改造', '党大会', 'FOMC', 'ECB', '国連総会', '中国政策会議', '中央経済工作会議', 'OPEC', '地政学', '波及経路', 'リスク管理'],
  },
  {
    indicatorId: 'year-end-central-banks',
    title: '年末の主要中銀イベントと来年テーマの先取り',
    country: 'market',
    category: 'anomaly',
    summary: '12月はFOMC・ECB・BOE・日銀の年内最終会合が集中し、市場の関心が「今回の決定」から「来年の政策パス・景気・資金フロー」へ移る時期。中銀間の方向性比較と、価格がどのテーマ（利下げ期待／日銀正常化／円キャリー巻き戻し／リバランスなど）に最も強く反応しているかを確認する実務指針。',
    loadContent: loadMd('market/year-end-central-banks.md'),
    relatedIndicators: ['anomaly-guide', 'summer-market-reaction', 'autumn-political-risk', 'rebalance', 'flow-knowledge'],
    tags: ['年末相場', '12月', 'FOMC', 'ECB', 'BOE', '日銀', '年内最終会合', '中央銀行', '中銀イベント', '来年テーマ', '政策パス', '利下げ期待', '利上げ', 'ソフトランディング', '日銀正常化', '円キャリー', 'リバランス', '年末ポジション調整', '流動性低下', '薄商い', 'ドル高', 'ドル安', 'ゴールド'],
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
    indicatorId: 'nikkei225-options',
    title: '日経225オプション',
    country: 'market',
    category: 'options',
    summary: 'JPX/OSEの日経225指数オプション（SQ・差金決済、250円刻み・125円刻み行使価格）。ATM IV、IVスマイル、25D RR/Fly、建玉・出来高P/C比、ターム構造で市場参加者のリスク織り込みと需給を読む。',
    loadContent: loadMd('market/nikkei225-options.md'),
    relatedIndicators: ['options-guide', 'vix-futures-curve', 'implied-vol-premium'],
    tags: ['日経225オプション', 'Nikkei 225 Options', 'JPX', 'OSE', 'SQ', 'ATM IV', 'IVスマイル', '25D RR', '25D Fly', '建玉', 'OI', 'Open Interest', '出来高', 'P/C比', 'ターム構造', 'Greeks', 'デルタ', 'ガンマ', 'DTE', '権利行使価格', '清算価格', '理論価格', 'JSCC'],
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
    indicatorId: 'options-optioncharts',
    title: 'OptionChartsの見方',
    country: 'market',
    category: 'options',
    summary: 'OptionCharts.ioの読み方。OI/Volume/GEX/DEX/Skew/Max Pain/Unusual Activityをチャート節目と組み合わせる実務手順。',
    loadContent: loadMd('market/options-optioncharts.md'),
    relatedIndicators: ['options-guide', 'options-tradingview', 'gex-dix'],
    tags: ['OptionCharts', 'OI', 'Open Interest', 'Volume', 'GEX', 'DEX', 'Gamma Exposure', 'Delta Exposure', 'Volatility Skew', 'Max Pain', 'Unusual Option Activity', 'Option Chain', 'Put-Call Ratio', '0DTE', 'SPY', 'QQQ', 'Call Wall', 'Put Wall', 'Gamma Flip'],
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
    indicatorId: 'vix-futures-curve',
    title: 'VIX先物カーブ（M1-M3）の見方',
    country: 'market',
    category: 'equities',
    summary: 'Cboe Futures Exchange（CFE）の月次VIX先物 VX1/VX2/VX3 のSettlementから、フロントスプレッド（VX1−VX2）、曲率（VX1−2×VX2+VX3）、M1-M3スロープ（VX1−VX3）を確認。コンタンゴ／バックワーデーション、VXX/UVXY等ロング系とSVXYインバース系のロール環境、M1 DTEの効きをDTE別パーセンタイルで読む。',
    loadContent: loadMd('market/vix-futures-curve.md'),
    relatedIndicators: ['gex-dix', 'options-guide', 'fear-greed', 'implied-vol-premium', 'cboe-realized-vol-gamma'],
    tags: ['VIX先物', 'VX1', 'VX2', 'VX3', 'フロントスプレッド', '曲率', 'M1-M3スロープ', 'カーブ', 'タームストラクチャー', 'コンタンゴ', 'バックワーデーション', 'Cboe', 'CFE', 'VXX', 'VIXY', 'UVXY', 'SVXY', 'インバースVIX', 'ロール', 'DTE', '月次限月', '週次限月', 'Settlement', 'VIX3M'],
  },
  {
    indicatorId: 'implied-vol-premium',
    title: 'インプライドボラプレミアム（VIX − HV）',
    country: 'market',
    category: 'equities',
    summary: 'VIX（30日先期待変動率）と S&P 500のヒストリカル・ボラティリティ（HV20/HV30）を比較。VIX−HVとVIX/HVでオプション市場のリスクプレミアム、ヘッジ需要、HV20とHV30の関係で実現ボラの加速・減速を読む。',
    loadContent: loadMd('market/implied-vol-premium.md'),
    relatedIndicators: ['vix-futures-curve', 'gex-dix', 'options-guide', 'fear-greed'],
    tags: ['インプライドボラ', 'インプライドボラティリティ', 'IV', 'ヒストリカルボラティリティ', 'HV', 'HV20', 'HV30', 'VIX', 'ボラプレミアム', 'リスクプレミアム', 'ヘッジ', 'Cboe', 'S&P 500', 'SPX', 'オプション', '実現ボラ'],
  },
  {
    indicatorId: 'cboe-realized-vol-gamma',
    title: 'Cboe Realized Volatility Index（GAMMA）',
    country: 'market',
    category: 'equities',
    summary: 'SPXW週次オプションの最短期ATMストラドル5本をデルタヘッジしたポートフォリオのトータルリターン指数。短期SPXオプションのロング・ガンマ／ロング・ボラ戦略がどの程度有利かを測る。GEX（ディーラーのガンマエクスポージャー）とは別物。',
    loadContent: loadMd('market/cboe-realized-vol-gamma.md'),
    relatedIndicators: ['vix-futures-curve', 'implied-vol-premium', 'gex-dix', 'options-guide'],
    tags: ['GAMMA', 'Cboe Realized Volatility Index', '実現ボラティリティ', 'SPXW', '週次オプション', 'ATMストラドル', 'デルタヘッジ', 'ロング・ガンマ', 'ガンマ・スキャルピング', '短期ボラ', '0DTE', 'Cboe', 'SPX', 'GEX', 'ディーラー'],
  },
  {
    indicatorId: 'cboe-implied-correlation-cor3m',
    title: 'Cboe 3-Month Implied Correlation Index（COR3M）',
    country: 'market',
    category: 'equities',
    summary: 'SPX指数オプションと上位50構成銘柄の個別株オプションのインプライド・ボラティリティから算出するCboeのインプライド相関指数。S&P500構成銘柄が今後3カ月で同方向に動きやすいか（システマティックリスク／分散効果）を測る。',
    loadContent: loadMd('market/cboe-implied-correlation-cor3m.md'),
    relatedIndicators: ['cboe-realized-vol-gamma', 'vix-futures-curve', 'implied-vol-premium', 'sector-ratio', 'correlation-guide'],
    tags: ['COR3M', 'Cboe Implied Correlation', 'インプライド相関', '相関指数', 'システマティックリスク', '分散効果', 'ディスパージョン', '上位50銘柄', 'SPX', 'S&P 500', 'ペアワイズ相関', 'インプライドボラ', 'IV', '3カ月', 'Cboe', 'リスクオフ'],
  },
  {
    indicatorId: 'advance-decline-mcclellan',
    title: 'A/Dライン・マクレランオシレーター',
    country: 'market',
    category: 'equities',
    summary: '米国株式市場のマーケット・ブレッドス指標。A/Dラインは上昇銘柄数−下落銘柄数の累積で市場参加度の中長期トレンドを、マクレランオシレーターはそのMACD型派生で短期モメンタムを測る。指数とのダイバージェンス、ブレッドス・スラストが代表的な見方。',
    loadContent: loadMd('market/advance-decline-mcclellan.md'),
    relatedIndicators: ['sp500-stock-portion', 'advance-decline-ratio', 'sector-ratio', 'fear-greed', 'naaim'],
    tags: ['A/Dライン', 'Advance/Decline Line', 'AD Line', 'マクレランオシレーター', 'McClellan Oscillator', 'ブレッドス', 'マーケットブレッドス', 'Net Advances', 'NYSE', 'Nasdaq', 'NYMO', 'NAMO', 'ratio-adjusted', 'ブレッドス・スラスト', 'ダイバージェンス', '市場内部', '時価総額加重', 'StockCharts'],
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

  // --- 英国 / BOEの見方（概要） ---
  {
    indicatorId: 'uk-boe-overview',
    title: 'イギリスとBOEの見方',
    country: 'uk',
    category: 'policy',
    summary: 'BOEはCPI2％の対称目標を最優先。FRB・ECBへの機械的追随ではなく国内インフレ・需要への波及で判断。サービスインフレ・賃金・家計消費の弱さ・労働需給が重要な確認項目。',
    loadContent: loadMd('uk/uk-boe-overview.md'),
    relatedIndicators: ['uk-ppi', 'uk-boe-inflation-attitudes', 'uk-pmi'],
    tags: ['BOE', 'イングランド銀行', '英国', 'ポンド', 'GBP', 'MPC', 'CPI', 'サービスインフレ', '賃金', '家計消費', 'Dhingra', 'OIS', 'FRB', 'ECB'],
  },

  // --- 英国 / SONIA ---
  {
    indicatorId: 'sonia',
    title: 'SONIA（英国）',
    country: 'uk',
    category: 'policy',
    summary: 'BoE管理の無担保翌日物RFR。Bank Rate近辺で推移し、政策金利の市場伝播を確認する基礎指標。SONIA OISを通じた将来の利下げ・利上げ期待の把握が実務上重要。',
    loadContent: loadMd('uk/uk-sonia.md'),
    relatedIndicators: ['uk-boe-overview', 'boe-mortgage-rates', 'uk-boe-inflation-attitudes'],
    tags: ['英国', 'SONIA', 'BoE', 'Bank Rate', 'OIS', 'RFR', '翌日物', '短期金利', 'LIBOR', 'ポンド', 'GBP'],
  },

  // --- 英国 / 公的部門純借入（PSNB） ---
  {
    indicatorId: 'uk-public-sector-net-borrowing',
    title: '公的部門純借入（PSNB）',
    country: 'uk',
    category: 'policy',
    summary: 'ONS公表の英国財政赤字指標。経常赤字＋純投資で構成され、純借入（フロー）と純債務（ストック）を区別。GDP比・季節性・改定リスクを踏まえて読む。',
    loadContent: loadMd('uk/uk-public-sector-net-borrowing.md'),
    relatedIndicators: ['uk-boe-overview', 'sonia', 'uk-economic-activity'],
    tags: ['PSNB', '公的部門純借入', 'Public Sector Net Borrowing', 'ONS', '英国', '財政赤字', '純債務', 'PSNFL', '自己申告所得税', 'VAT', 'PAYE', '会計年度', 'GDP比', '財政ルール'],
  },

  // --- 英国 / APFギルト保有残高（QT） ---
  {
    indicatorId: 'uk-qt',
    title: 'APFギルト保有残高（QT）',
    country: 'uk',
    category: 'policy',
    summary: 'BoE Asset Purchase Facilityの保有ギルト残高（initial purchase proceedsベース）。満期償還停止と能動売却によるQT進捗を読む。市場価格と混同しない。',
    loadContent: loadMd('uk/uk-qt.md'),
    relatedIndicators: ['uk-boe-overview', 'sonia', 'uk-public-sector-net-borrowing'],
    tags: ['APF', 'Asset Purchase Facility', 'BEAPFF', 'ギルト', 'gilts', 'QT', '量的引き締め', 'QE', '量的緩和', 'BoE', 'イングランド銀行', 'MPC', 'initial purchase proceeds', 'HMT', '財務省補償', 'Bank Rate'],
  },

  // --- 英国 / 小売売上高 ---
  {
    indicatorId: 'uk-retail-sales',
    title: '小売売上高（英国）',
    country: 'uk',
    category: 'consumer',
    summary: 'ONSの数量ベース小売売上高。GfK消費者信頼感と組み合わせて家計部門の景況感と消費動向を整理する。前年比では一定の連動性があるが、前月比では短期要因が大きく相関は弱い。',
    loadContent: loadMd('uk/uk-retail-sales.md'),
    relatedIndicators: ['uk-gfk-consumer-confidence'],
    tags: ['英国', '小売売上', 'ONS', 'Retail Sales', 'GfK', '消費者信頼感', '家計', '消費', 'ポンド', 'GBP'],
  },

  // --- 英国 / CPIH ---
  {
    indicatorId: 'uk-cpih',
    title: 'CPIH（英国）',
    country: 'uk',
    category: 'inflation',
    summary: 'ONSが主たるインフレ指標と位置づける包括的物価指数。CPIに持ち家居住者住宅費とCouncil Taxを加えたもの。BOEの政策目標はCPIだが、家計の物価実感把握にはCPIHが有用。',
    loadContent: loadMd('uk/uk-cpih.md'),
    relatedIndicators: ['uk-ppi', 'uk-boe-inflation-attitudes', 'uk-boe-overview'],
    tags: ['英国', 'CPIH', 'CPI', 'ONS', 'OOH', 'Council Tax', '住宅費', 'インフレ', 'BOE', 'ポンド', 'GBP'],
  },

  // --- 英国 / BRC店頭価格指数 ---
  {
    indicatorId: 'uk-brc-shop-price',
    title: 'BRC店頭価格指数（SPM・英国）',
    country: 'uk',
    category: 'inflation',
    summary: 'BRCが毎月公表する500品目ベースの店頭価格指標。ONS公式CPIより約10日早く、食品・非食品の財価格圧力を先行的に把握できる。サービス価格や住宅費は捉えない。',
    loadContent: loadMd('uk/uk-brc-shop-price.md'),
    relatedIndicators: ['uk-cpih', 'uk-ppi', 'uk-boe-overview'],
    tags: ['英国', 'BRC', 'Shop Price', 'SPM', '店頭価格', 'インフレ', '食品', '非食品', 'CPI', '先行指標', 'ポンド', 'GBP'],
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
    summary: '消費者のインフレ懸念が賃上げ圧力を強める経路がある。期待インフレ・実際の物価・賃金の3点を合わせて確認するのが基本。サービスCPIとの関係も重要。',
    loadContent: loadMd('uk/uk-boe-inflation-attitudes.md'),
    relatedIndicators: ['uk-ppi', 'uk-wages', 'uk-boe-overview'],
    tags: ['BOE', 'インフレ期待', '賃金', '英国', 'サービスCPI', 'ONS', '賃上げ圧力', 'CPI', 'ポンド', 'GBP'],
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

  // --- 英国 / 住宅市場 ---
  {
    indicatorId: 'uk-housing-market',
    title: '英国住宅市場',
    country: 'uk',
    category: 'housing',
    summary: '英国は家計債務に占める住宅ローンの比重が大きく、BOEも住宅市場を金利政策・金融安定・家計行動と結びつけて重視。需要は承認件数→価格→着工の順で遅れて波及し、affordability悪化時は追い風とは限らない。',
    loadContent: loadMd('uk/uk-housing-market.md'),
    relatedIndicators: ['uk-boe-overview', 'uk-boe-inflation-attitudes'],
    tags: ['英国', '住宅', 'BOE', 'イングランド銀行', '住宅ローン', 'Mortgage', 'affordability', '住宅価格', 'HMRC', '家計消費', '信用循環', '建設', 'ポンド', 'GBP'],
  },

  // --- 英国 / 住宅ローン承認件数 ---
  {
    indicatorId: 'boe-mortgage-lending',
    title: '住宅ローン承認件数（英国）',
    country: 'uk',
    category: 'housing',
    summary: '住宅価格指数に1〜7か月先行しやすい需要指標。3か月平均で見ると Halifax・Nationwide・UK HPI との相関0.48〜0.56。増加率は価格前年比に半年超先行。',
    loadContent: loadMd('uk/uk-boe-mortgage-lending.md'),
    relatedIndicators: ['uk-housing-market', 'uk-house-price', 'halifax-house-price', 'nationwide-hpi'],
    tags: ['英国', '住宅ローン', 'Mortgage', 'BoE', '承認件数', '住宅価格', '先行指標', 'Halifax', 'Nationwide'],
  },

  // --- 英国 / 住宅ローン金利 ---
  {
    indicatorId: 'boe-mortgage-rates',
    title: '住宅ローン金利（英国）',
    country: 'uk',
    category: 'housing',
    summary: 'BoEの実効金利（残高ベース・新規固定）と提示金利（SVR/revert-to rate）の3系列。new businessとoutstandingの違い、実効vs提示の使い分けが重要。',
    loadContent: loadMd('uk/uk-boe-mortgage-rates.md'),
    relatedIndicators: ['boe-mortgage-lending', 'uk-housing-market', 'uk-boe-overview'],
    tags: ['英国', '住宅ローン', 'Mortgage', 'BoE', '実効金利', 'SVR', '固定金利', '変動金利', '住宅', 'ポンド', 'GBP'],
  },

  // --- 英国 / 平均週給（賃金） ---
  {
    indicatorId: 'uk-wages',
    title: '平均週給（英国）',
    country: 'uk',
    category: 'employment',
    summary: 'BOEが賃金をサービス価格の持続性や国内コスト圧力の核心指標として重視。民間部門の通常賃金（賞与除く）が特に注目される。',
    loadContent: loadMd('uk/uk-wages.md'),
    relatedIndicators: ['uk-unemployment', 'uk-unit-labour-costs', 'uk-boe-overview'],
    tags: ['英国', '賃金', 'BOE', 'ONS', '平均週給', 'Average Weekly Earnings', 'AWE', 'サービスインフレ', 'ポンド', 'GBP', 'MPC'],
  },

  // --- 英国 / 失業率 ---
  {
    indicatorId: 'uk-unemployment',
    title: '失業率（英国）',
    country: 'uk',
    category: 'employment',
    summary: '均衡失業率は固定的な境界線ではなく、賃金・求人・雇用者数・労働参加と総合的に判断する必要がある。LFS単独ではなくClaimant Count・PAYE RTIと併用。',
    loadContent: loadMd('uk/uk-unemployment.md'),
    relatedIndicators: ['uk-wages', 'uk-claimant-count', 'uk-employment', 'uk-economic-activity'],
    tags: ['英国', '失業率', 'BOE', 'ONS', 'LFS', 'Claimant Count', 'PAYE', '労働市場', '均衡失業率', 'ポンド', 'GBP'],
  },

  // --- 英国 / 単位労働コスト ---
  {
    indicatorId: 'uk-unit-labour-costs',
    title: '単位労働コスト（英国）',
    country: 'uk',
    category: 'employment',
    summary: 'サービスインフレの背景にあるコスト圧力を見る補助指標。賃金上昇が生産性改善を上回るとき企業コスト圧力が高まる。',
    loadContent: loadMd('uk/uk-unit-labour-costs.md'),
    relatedIndicators: ['uk-wages', 'uk-productivity', 'uk-boe-overview'],
    tags: ['英国', 'ULC', '単位労働コスト', 'Unit Labour Costs', 'BOE', '生産性', 'サービスインフレ', '賃金', 'ポンド', 'GBP'],
  },

  // --- 英国 / 経済活動率 ---
  {
    indicatorId: 'uk-economic-activity',
    title: '経済活動率（英国）',
    country: 'uk',
    category: 'employment',
    summary: '労働力人口の人口比。失業率だけでは見えない労働市場への参加・退出を把握する指標。経済非活動率の内訳（長期疾病等）も重要。LFS単独ではなくClaimant Count・PAYE RTIと併用。',
    loadContent: loadMd('uk/uk-economic-activity.md'),
    relatedIndicators: ['uk-unemployment', 'uk-wages', 'uk-boe-overview'],
    tags: ['英国', '経済活動率', 'ONS', 'LFS', '労働参加', '非活動', '長期疾病', '労働供給', '賃金圧力', 'BOE', 'ポンド', 'GBP'],
  },

  // --- 英国 / 政府債務残高対GDP比 ---
  {
    indicatorId: 'uk-government-debt-to-gdp-ratio',
    title: '政府債務残高対GDP比（英国）',
    country: 'uk',
    category: 'economy',
    summary: 'ONS HF6X（PSND ex GDP比）。狭義の純債務／GDPで財政余力を見る。財政ルールで使われるPSNFLとは別物。利払い費・OBR見通し・国債利回りと併読。',
    loadContent: loadMd('uk/uk-government-debt-to-gdp-ratio.md'),
    relatedIndicators: ['uk-public-sector-net-borrowing', 'uk-qt', 'uk-boe-overview'],
    tags: ['英国', '政府債務残高', 'PSND', 'PSNFL', 'GDP比', 'HF6X', 'ONS', '財政健全性', '財政ルール', 'OBR', '利払い費', '国債発行', '純債務'],
  },

  // --- カナダ / 経済概要 ---
  {
    indicatorId: 'canada-overview',
    title: 'カナダ経済の特徴',
    country: 'canada',
    category: 'economy',
    summary: '資源国かつサービス経済の二面性。輸出の約4分の3が米国向けで対米関係が最重要。オイルサンド、自動車産業、移民による人口増加、量子技術など多面的な構造を持つ。',
    loadContent: loadMd('canada/canada-overview.md'),
    relatedIndicators: ['ivey-pmi', 'ippi', 'ca-sp-pmi'],
    tags: ['カナダ', '経済概要', '資源国', 'オイルサンド', '自動車', '移民', '量子技術', 'CAD', 'アメリカ', 'アルバータ', 'オンタリオ'],
  },

  // --- カナダ / 貿易構造 ---
  {
    indicatorId: 'ca-trade-balance',
    title: '貿易構造の見方（カナダ）',
    country: 'canada',
    category: 'economy',
    summary: '輸出の75.9%が米国向け。エネルギー（88%米国向け）と自動車（94%米国向け）が中核。Trade/GDPは約65%で外需感応度が高い。統計の定義差にも注意。',
    loadContent: loadMd('canada/canada-trade.md'),
    relatedIndicators: ['canada-overview', 'trade-balance'],
    tags: ['カナダ', '貿易', '輸出', '輸入', 'エネルギー', '自動車', '米国', '対米依存', 'Statistics Canada', 'CAD', '原油', 'オイルサンド'],
  },

  // --- カナダ / CPI住居費・輸送費 ---
  {
    indicatorId: 'cpi-service-rent',
    title: 'CPI住居費・輸送費の位置づけ（カナダ）',
    country: 'canada',
    category: 'inflation',
    summary: '住居（約29%）と輸送（約17%）がCPIバスケットの主要項目。住居は粘着的で基調インフレを映し、輸送はガソリン等で短期変動を生みやすい。両者を分けて見ることが重要。',
    loadContent: loadMd('canada/canada-cpi-shelter-transport.md'),
    relatedIndicators: ['ippi', 'canada-overview'],
    tags: ['カナダ', 'CPI', '住居費', 'Shelter', '輸送', 'Transportation', 'ガソリン', '家賃', 'インフレ', 'Statistics Canada', 'CAD'],
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

  // --- カナダ / CORRA ---
  {
    indicatorId: 'ca-corra',
    title: 'CORRA（翌日物レポ平均金利）',
    country: 'canada',
    category: 'policy',
    summary: 'Bank of Canada公表のカナダドル翌日物担保付レポ平均金利。CDORの代替リスクフリー金利で、政策金利との乖離・パーセンタイル・分布からレポ需給を読む。',
    loadContent: loadMd('canada/ca-corra.md'),
    relatedIndicators: ['canada-overview', 'ivey-pmi'],
    tags: ['カナダ', 'CORRA', 'Canadian Overnight Repo Rate Average', 'Bank of Canada', 'BoC', '翌日物', 'レポ', '担保付き', 'リスクフリー金利', 'CDOR', 'Term CORRA', 'CARR', 'CORRA Compounded Index', 'T+1', '政策金利', '短期金利', 'CAD'],
  },

  // --- カナダ / 決済残高 ---
  {
    indicatorId: 'ca-settlement-balances',
    title: '決済残高（Settlement Balances）',
    country: 'canada',
    category: 'policy',
    summary: 'Lynx参加金融機関がBank of Canadaに保有する決済用預金。フロア・システムの中核で、CORRAの安定性とQE/QTの進捗を読む流動性指標。',
    loadContent: loadMd('canada/ca-settlement-balances.md'),
    relatedIndicators: ['ca-corra', 'canada-overview'],
    tags: ['カナダ', '決済残高', 'Settlement Balances', 'Lynx', 'LVTS', 'Bank of Canada', 'BoC', 'Payments Canada', 'フロア・システム', '中央銀行準備', '預金金利', 'オペレーティング・バンド', 'QE', 'QT', 'CORRA', '流動性', 'CAD'],
  },

  // --- カナダ / 政府預金 ---
  {
    indicatorId: 'ca-government-deposits',
    title: '政府預金（Government Deposits）',
    country: 'canada',
    category: 'policy',
    summary: 'カナダ政府のカナダドル現金残高（BoC保有分＋オークション参加者保有分）。決済残高・CORRAと組み合わせて短期金融市場の流動性吸収・放出を読む。',
    loadContent: loadMd('canada/ca-government-deposits.md'),
    relatedIndicators: ['ca-settlement-balances', 'ca-corra', 'canada-overview'],
    tags: ['カナダ', '政府預金', 'Government Deposits', 'Receiver General', 'Bank of Canada', 'BoC', '財務代理人', 'Lynx', 'オークション', '現金管理', '流動性', '国債発行', '償還', '税収', 'CORRA', 'CAD'],
  },

  // --- カナダ / 家計債務返済比率（DSR） ---
  {
    indicatorId: 'ca-debt-service-ratio',
    title: '家計債務返済比率（DSR）',
    country: 'canada',
    category: 'housing',
    summary: 'Statistics Canada公表の家計DSR。義務的な元本返済＋利払いを可処分所得比で測る。住宅ローン／非住宅ローンに分解可能で、家計のキャッシュフロー負担と金利感応度を測る中核指標。',
    loadContent: loadMd('canada/ca-debt-service-ratio.md'),
    relatedIndicators: ['ca-corra', 'canada-overview'],
    tags: ['カナダ', '家計債務返済比率', 'DSR', 'Debt Service Ratio', 'Statistics Canada', '11-10-0065-01', '可処分所得', '住宅ローン', '非住宅ローン', 'HELOC', '消費者信用', '家計債務', '金利感応度', '住宅市場', '信用リスク', 'CAD'],
  },

  // --- 中国 / 7日物リバースレポ金利 ---
  {
    indicatorId: 'reverse-repo-rate',
    title: '7日物リバースレポ金利（中国）',
    country: 'china',
    category: 'policy',
    summary: 'PBoCが2024年7月に政策利率として明確化した中核金利。LPRはこれを上流として参照、MLFは中期流動性供給手段へ役割分担。DR007の政策金利周辺での推移が伝達効果の確認材料。',
    loadContent: loadMd('china/cn-reverse-repo-rate.md'),
    relatedIndicators: ['cn-overview', 'cn-gdp'],
    tags: ['中国', 'リバースレポ', '7日物', '逆回购', 'PBoC', '人民銀行', '政策金利', 'LPR', 'MLF', 'DR007', '短期金利', 'CNY'],
  },

  // --- 中国 / 預金準備率（RRR） ---
  {
    indicatorId: 'rrr',
    title: '預金準備率（大型金融機関）',
    country: 'china',
    category: 'policy',
    summary: 'PBoCの大型金融機関向け預金準備率。「三档两优」枠組みの区分別準備率で、加重平均RRR・MLF・LPR・社会融資総量と併読し、流動性供給姿勢を読む。',
    loadContent: loadMd('china/cn-rrr.md'),
    relatedIndicators: ['reverse-repo-rate', 'cn-overview', 'm1-m2', 'cn-credit-impulse'],
    tags: ['中国', '預金準備率', 'RRR', '法定準備率', '降準', 'PBoC', '人民銀行', '大型金融機関', '三档两优', '加重平均準備率', '流動性供給', '社会融資総量', 'MLF', 'LPR', 'CNY'],
  },

  // --- 中国 / Fixing Repo Rate ---
  {
    indicatorId: 'fixing-repo-rate',
    title: 'Fixing Repo Rate (FR / FDR)',
    country: 'china',
    category: 'policy',
    summary: 'CFETS公表の銀行間レポ固定金利（FR）と預金取扱金融機関レポ固定金利（FDR）。FR007/FDR007を中心に短期流動性と政策金利波及を確認する。',
    loadContent: loadMd('china/cn-fixing-repo-rate.md'),
    relatedIndicators: ['reverse-repo-rate', 'rrr', 'cn-overview'],
    tags: ['中国', 'Fixing Repo Rate', 'FR001', 'FR007', 'FR014', 'FDR001', 'FDR007', 'FDR014', 'CFETS', 'ChinaMoney', 'DR007', 'SHIBOR', 'レポ', '銀行間市場', '短期金利', '流動性'],
  },

  // --- 中国 / Central Parity Rate ---
  {
    indicatorId: 'central-parity',
    title: 'Central Parity Rate（USD/CNY基準値）',
    country: 'china',
    category: 'policy',
    summary: 'CFETS公表の人民元対米ドル公式基準値（Fixing）。管理変動相場の中心レートで、上下2%の許容幅、スポット・CNHとの乖離から当局の為替政策スタンスを読む。',
    loadContent: loadMd('china/cn-central-parity.md'),
    relatedIndicators: ['fixing-repo-rate', 'reverse-repo-rate', 'rrr', 'cn-overview'],
    tags: ['中国', 'Central Parity Rate', 'USD/CNY', '基準値', 'Fixing', 'PBoC', 'CFETS', '人民元', 'CNY', 'CNH', '管理変動相場', 'バンド', '上下2%', '通貨バスケット', '資本流出'],
  },

  // --- 中国 / SHIBOR ---
  {
    indicatorId: 'shibor',
    title: 'SHIBOR（上海銀行間取引金利）',
    country: 'china',
    category: 'policy',
    summary: '上海銀行間同業拆放利率（O/N〜1Y）。18行報価の上下4行除外平均で算出される無担保銀行間金利。短期は流動性、長期は中期資金コストを示す。',
    loadContent: loadMd('china/cn-shibor.md'),
    relatedIndicators: ['fixing-repo-rate', 'reverse-repo-rate', 'rrr', 'central-parity'],
    tags: ['中国', 'SHIBOR', '上海銀行間取引金利', '银行间', '無担保', '報価銀行', '全国銀行間同業拆借中心', 'O/N', '1W', '1M', '3M', '1Y', '短期金利', '銀行間流動性', '金利カーブ'],
  },

  // --- 中国 / 新規人民元貸出 ---
  {
    indicatorId: 'new-rmb-loans',
    title: '新規人民元貸出',
    country: 'china',
    category: 'policy',
    summary: 'PBOC公表の人民元貸出ネット増加額。家計・企業・短期/中長期/手形の内訳と社会融資総量（AFRE）と組み合わせて、銀行信用循環を読む。1月・四半期末の季節性に注意。',
    loadContent: loadMd('china/cn-new-rmb-loans.md'),
    relatedIndicators: ['m1-m2', 'cn-credit-impulse', 'rrr', 'reverse-repo-rate'],
    tags: ['中国', '新規人民元貸出', '新增人民币贷款', 'New RMB Loans', 'PBoC', '人民銀行', '銀行貸出', '家計向け', '企業向け', '中長期貸出', '短期貸出', '手形融資', '社会融資総量', 'AFRE', 'TSF', '住宅ローン', '信用供給'],
  },

  // --- 中国 / 国債発行 ---
  {
    indicatorId: 'bond-issuance',
    title: '国債発行（Government Bond Issuance）',
    country: 'china',
    category: 'policy',
    summary: '中国財政部公表の国債入札予定・結果・月次供給量。記帳式/貼現/貯蓄国債を区別し、年限構成・落札利回り・特別国債の有無から債券需給と財政動向を読む。',
    loadContent: loadMd('china/cn-bond-issuance.md'),
    relatedIndicators: ['new-rmb-loans', 'reverse-repo-rate', 'rrr', 'cn-overview'],
    tags: ['中国', '国債発行', 'Government Bond Issuance', '中国財政部', 'MOF', '入札', '記帳式国債', '附息国債', '貼現国債', '貯蓄国債', '特別国債', '落札利回り', '票面利率', '修正的多重価格', '年限構成', '債券需給', '長期金利'],
  },

  // --- 中国 / 資本フロー（SAFE） ---
  {
    indicatorId: 'capital-flows',
    title: '資本フロー（SAFE：銀行代客涉外收付款）',
    country: 'china',
    category: 'policy',
    summary: 'SAFE公表の銀行代客涉外收付款。国内非銀行部門と非居住者の資金受払を経常/資本・金融/証券投資別に把握し、人民元・中国株・コモディティへの波及を読む。',
    loadContent: loadMd('china/cn-capital-flows.md'),
    relatedIndicators: ['central-parity', 'bond-issuance', 'new-rmb-loans', 'cn-overview'],
    tags: ['中国', '資本フロー', 'Capital Flows', 'SAFE', '国家外貨管理局', '銀行代客涉外收付款', '銀行結售匯', '経常勘定', '資本金融勘定', '証券投資', '貨物貿易', 'サービス', '人民元', '資本流出', 'クロスボーダー決済', '国際収支'],
  },

  // --- 中国 / 海外投資家フロー（中国債券） ---
  {
    indicatorId: 'overseas-investor-flow',
    title: '海外投資家フロー（中国債券）',
    country: 'china',
    category: 'policy',
    summary: 'Bond Connect公表のCCDC・SHCH月末海外投資家債券保有残高。中国債券への海外資金需要を月次フローの代理指標として読む。為替ヘッジコストとあわせて確認。',
    loadContent: loadMd('china/cn-overseas-investor-flow.md'),
    relatedIndicators: ['capital-flows', 'bond-issuance', 'central-parity', 'cn-overview'],
    tags: ['中国', '海外投資家フロー', 'Foreign Holdings', 'Bond Connect', 'CCDC', 'SHCH', '中国債券', '中国国債', '政策性金融債', '銀行間市場', 'Bloomberg Barclays', '指数組入', '為替ヘッジ', '資本流入', '人民元'],
  },

  // --- 中国 / 地方債 ---
  {
    indicatorId: 'cn-local-bonds',
    title: '地方債（中国地方政府債券）',
    country: 'china',
    category: 'policy',
    summary: '中国財政部公表の地方政府債券発行・残高。新規/再融資・一般/専項の内訳と枠余地から、財政出動・インフラ投資・地方債務管理を読み分ける。',
    loadContent: loadMd('china/cn-local-bonds.md'),
    relatedIndicators: ['bond-issuance', 'new-rmb-loans', 'cn-overview', 'cn-fixed-asset-investment'],
    tags: ['中国', '地方債', '地方政府債券', '中国財政部', 'MOF', '一般債券', '専項債券', '新規債', '再融資債', '化債', '隠性債務', '債務限度額', '枠余地', '平均発行利率', 'インフラ投資', '財政出動'],
  },

  // --- 中国 / 政策運営と景気の見方 ---
  {
    indicatorId: 'cn-overview',
    title: '中国の政策運営と景気の見方',
    country: 'china',
    category: 'policy',
    summary: '中央政治局会議（4・7・12月が節目）の文言変化が重要な政策シグナル。米国景気は外需改善要因だが、国内の不動産・消費・信用が決定的。PBoCの「穏健」は中立を意味せず、RRR・政策金利・信用支援の実務で判断。',
    loadContent: loadMd('china/cn-overview.md'),
    relatedIndicators: ['cn-ppi', 'cn-pmi', 'cn-m1-m2'],
    tags: ['中国', '政治局会議', 'PBoC', '中国人民銀行', 'RRR', '預金準備率', '政策金利', '不動産', '内需', '外需', 'CNY', '共産党'],
  },

  // --- 中国 / GDPの見方 ---
  {
    indicatorId: 'cn-gdp',
    title: 'GDPの見方（中国）',
    country: 'china',
    category: 'economy',
    summary: '2024年産業構成は第1次6.8%・第2次36.4%・第3次56.8%。サービス業中心だが工業が約3割で製造業・建設・輸出の影響大。不動産関連は広義でGDP約20%規模。2024年実質成長率5.0%。中身の分析が重要。',
    loadContent: loadMd('china/cn-gdp.md'),
    relatedIndicators: ['cn-overview', 'cn-ppi', 'cn-pmi', 'gdp'],
    tags: ['中国', 'GDP', '実質成長率', 'NBS', '国家統計局', 'サービス業', '工業', '不動産', '第3次産業', '最終消費', '固定資産投資', 'IMF', 'CNY'],
  },

  // --- 中国 / 固定資産投資 ---
  {
    indicatorId: 'fixed-asset-investment',
    title: '固定資産投資（中国）',
    country: 'china',
    category: 'economy',
    summary: 'GDP構成項目ではなく、投資需要を月次で測る景気指標。固定資本形成総額とは口径が異なる（土地取得費・500万元以上プロジェクトなど）。インフラ・製造業・不動産・民間の内訳確認が重要。',
    loadContent: loadMd('china/cn-fixed-asset-investment.md'),
    relatedIndicators: ['cn-gdp', 'cn-overview'],
    tags: ['中国', '固定資産投資', 'FAI', 'NBS', 'インフラ投資', '製造業投資', '不動産開発投資', '民間投資', '資本形成', '月次指標', 'CNY'],
  },

  // --- 中国 / 土地売却収入 ---
  {
    indicatorId: 'cn-land-sales-income',
    title: '土地売却収入（中国）',
    country: 'china',
    category: 'economy',
    summary: '中国財政部公表の国有土地使用権出譲収入。地方政府の政府性基金予算の主要財源で、不動産デベロッパーの土地取得意欲と地方財政余力を読む土地財政の中核指標。',
    loadContent: loadMd('china/cn-land-sales-income.md'),
    relatedIndicators: ['cn-commercial-residential-sales', 'cn-fixed-asset-investment', 'cn-local-bonds', 'cn-overview'],
    tags: ['中国', '土地売却収入', '国有土地使用権出譲収入', '土地出譲', '土地財政', '中国財政部', '政府性基金予算', '地方政府', '不動産', 'デベロッパー', 'インフラ投資', '都市開発', '専項債', 'CNY'],
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

  // --- 中国 / 輸出価格 ---
  {
    indicatorId: 'cn-export-prices',
    title: '中国の輸出価格と世界の財インフレ',
    country: 'china',
    category: 'inflation',
    summary: '中国は世界の工場として完成品・中間財・部品を大量に輸出するため、輸出価格は各国の輸入物価を通じて財インフレに波及。為替・関税・物流・在庫・国内需要で最終的なCPI反映は変化し、サービスインフレへの影響は限定的。',
    loadContent: loadMd('china/cn-export-prices.md'),
    relatedIndicators: ['cn-ppi', 'cn-overview', 'cn-gdp', 'ppi', 'ecb-ppi'],
    tags: ['中国', '輸出価格', '輸出物価', '財インフレ', 'グローバルインフレ', '輸入物価', '中間財', '人民元', 'CNY', 'PPI', 'コモディティ', '海上運賃', '関税', 'ディスインフレ'],
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

  // --- 中国 / 李克強指数 ---
  {
    indicatorId: 'cn-li-keqiang-index',
    title: '李克強指数（中国）',
    country: 'china',
    category: 'economy',
    summary: '電力消費・鉄道貨物・銀行融資の3指標から中国の実体経済を捉える非公式指標（一般ウェイト例: 融資40%・電力40%・鉄道貨物20%）。工業・建設・素材需要・信用循環の方向感を見る補助指標で、サービス業・個人消費・デジタル経済は反映されにくい。',
    loadContent: loadMd('china/cn-li-keqiang-index.md'),
    relatedIndicators: ['cn-gdp', 'cn-overview', 'cn-pmi', 'cn-credit-impulse', 'm1-m2', 'fixed-asset-investment'],
    tags: ['李克強指数', 'Li Keqiang Index', '中国', '電力消費', '鉄道貨物', '銀行融資', 'GDP', '実体経済', '工業', '重工業', '建設', '信用', 'MacroMicro'],
  },

  // --- 中国 / Baidu人流・人口移動 ---
  {
    indicatorId: 'cn-baidu-migration',
    title: 'Baidu人流・人口移動データと非製造業の関係（中国）',
    country: 'china',
    category: 'economy',
    summary: '百度地図慧眼の位置情報データで都市間・地域間の人口移動を高頻度に把握。非製造業PMIのサービス業（交通・旅行・宿泊・外食・小売）を中心とした補助指標で、建設業は説明しにくい。春節・国慶節などの季節性に注意。',
    loadContent: loadMd('china/cn-baidu-migration.md'),
    relatedIndicators: ['cn-pmi', 'caixin-pmi', 'cn-overview', 'cn-gdp', 'cn-li-keqiang-index'],
    tags: ['Baidu', '百度', '百度遷徙', '百度地図慧眼', '人流', '人口移動', '中国', 'サービス業', '非製造業PMI', '都市活動', '春節', '国慶節', '高頻度データ', 'オルタナティブデータ'],
  },

  // --- 中国 / 商業住宅販売 ---
  {
    indicatorId: 'cn-commercial-residential-sales',
    title: '不動産販売面積と住宅価格の関係（中国）',
    country: 'china',
    category: 'housing',
    summary: '販売面積YoYは住宅価格YoYに対して3〜6か月（局面によっては6〜9か月）先行しやすい。需要悪化はまず取引量に出て、在庫増・値引き販売を経て価格に反映される。販売回復後も在庫処理が進むまで価格の戻りは遅れる。',
    loadContent: loadMd('china/cn-commercial-residential-sales.md'),
    relatedIndicators: ['fixed-asset-investment', 'cn-gdp', 'cn-overview', 'm1-m2', 'cn-credit-impulse'],
    tags: ['中国', '不動産', '住宅', '販売面積', '新規着工', '販売額', '住宅価格', 'NBS', 'デベロッパー', '先行指標', '在庫', 'CNY'],
  },

  // --- スイス / 概要 ---
  {
    indicatorId: 'ch-overview',
    title: 'スイス経済とスイスフランの見方',
    country: 'switzerland',
    category: 'economy',
    summary: '小規模な開放経済でEUが最重要の貿易相手。SNBは0〜2%の物価安定を最優先とし、フラン高/安の双方に対応。輸出の中核は化学・医薬品（52.7%）で、就業者の77.8%は第3次産業。フランは安全資産として有事に買われやすいが、SNBの姿勢と金利差まで含めて判断する必要がある。',
    loadContent: loadMd('switzerland/ch-overview.md'),
    relatedIndicators: ['ch-pmi', 'ch-ppi'],
    tags: ['スイス', 'CHF', 'スイスフラン', 'SNB', '物価安定', '化学', '医薬品', 'サービス業', 'EU', '安全資産', '有事', '為替', 'SECO', 'FSO'],
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

  // --- スイス / KOF先行指数 ---
  {
    indicatorId: 'kof-barometer',
    title: 'KOF先行指数（KOF Economic Barometer）',
    country: 'switzerland',
    category: 'consumer',
    summary: 'KOF Swiss Economic Instituteが毎月公表するスイスの景気先行総合指数。GDP月次成長率を参照系列に300超の経済系列を合成。100が平均で、上下から景気モメンタムを先回り把握する。',
    loadContent: loadMd('switzerland/kof-barometer.md'),
    relatedIndicators: ['ch-pmi', 'ch-overview'],
    tags: ['KOF', 'KOF Barometer', '先行指標', '景気', 'スイス', 'ETH Zurich', 'GDP', '景気循環', 'モメンタム', '製造業', '輸出'],
  },

  // --- スイス / SNB当座預金 ---
  {
    indicatorId: 'ch-sight-deposits',
    title: 'SNB当座預金（Sight Deposits with the SNB）',
    country: 'switzerland',
    category: 'policy',
    summary: 'SNB Data Portal公表の当座預金残高。スイスフラン市場の流動性、レポ取引、外貨購入・売却、SNB Billsの結果として動く。SARON誘導と為替介入の可能性を読むうえで重要な補助指標。',
    loadContent: loadMd('switzerland/ch-sight-deposits.md'),
    relatedIndicators: ['ch-overview'],
    tags: ['スイス', 'SNB当座預金', 'Sight Deposits', 'SNB', 'Swiss National Bank', 'SARON', '政策金利', 'SNB Bills', 'レポ取引', '流動性', '為替介入', 'CHF', '外貨準備', '最低準備', '付利', '銀行券', 'バランスシート'],
  },

  // --- スイス / 外貨準備 ---
  {
    indicatorId: 'ch-foreign-currency-reserves',
    title: '外貨準備（Foreign Currency Reserves）',
    country: 'switzerland',
    category: 'policy',
    summary: 'SNB保有の外貨建て運用資産（債券・株式・預金）。EUR 39%/USD 37%中心、政府債61%・株式28%。CHF高抑制のための外貨購入、為替介入、評価効果、CHF建て／USD建ての違いを読み解く中核指標。',
    loadContent: loadMd('switzerland/ch-foreign-currency-reserves.md'),
    relatedIndicators: ['ch-sight-deposits', 'ch-overview'],
    tags: ['スイス', '外貨準備', 'Foreign Currency Reserves', 'SNB', 'Swiss National Bank', '通貨準備', 'Currency Reserves', '外貨建て投資', 'EUR', 'USD', 'JPY', '政府債', '株式', '為替介入', 'CHF', '評価効果', 'バランスシート', 'IMF', 'SDR', '金', '安全資産'],
  },

  // --- スイス / 住宅ローン残高 ---
  {
    indicatorId: 'ch-mortgage-balance',
    title: '住宅ローン残高（Mortgage Loans）',
    country: 'switzerland',
    category: 'housing',
    summary: 'SNB銀行統計（Mortgage loans）公表のスイス銀行部門住宅ローン残高。銀行資産の最大項目（総資産の38.2%、国内融資の86.7%）。前年比・前月比で信用拡大ペースと住宅市場の過熱感を読む。',
    loadContent: loadMd('switzerland/ch-mortgage-balance.md'),
    relatedIndicators: ['ch-overview'],
    tags: ['スイス', '住宅ローン', '住宅ローン残高', 'Mortgage loans', 'SNB', 'Swiss National Bank', '銀行統計', '住宅市場', '不動産', '家計信用', '銀行貸出', '信用拡大', '金融安定', '不動産価格', 'CHF', 'Swiss Banking'],
  },

  // --- スイス / 新規住宅ローン融資限度額 ---
  {
    indicatorId: 'ch-new-mortgage-loans',
    title: '新規住宅ローンの融資限度額の合計金額',
    country: 'switzerland',
    category: 'housing',
    summary: 'SNB新規住宅ローン調査公表のフロー指標。スイス国内不動産向けに新規承認された住宅ローンの与信枠総額。購入・借換・建設資金を対象とし、住宅ローン需要・金融環境・金融安定リスクを読む。',
    loadContent: loadMd('switzerland/ch-new-mortgage-loans.md'),
    relatedIndicators: ['ch-mortgage-balance', 'ch-overview'],
    tags: ['スイス', '新規住宅ローン', '融資限度額', '与信枠', 'New mortgage loans', 'SNB', 'Swiss National Bank', '住宅市場', '不動産', '借換', '建設資金', '住宅ローン金利', 'LTV', '金融安定', '家計債務', '住宅信用'],
  },

  // --- ニュージーランド / 中銀制度概要 ---
  {
    indicatorId: 'nz-rbnz-overview',
    title: 'ニュージーランド中銀制度の見方',
    country: 'newzealand',
    category: 'policy',
    summary: 'RBNZはRemitに基づきMPCがOCRを決定。2023年12月に雇用目標を外し物価安定に再集中。インフレ目標は中期1〜3%・中心2%。雇用は引き続きインフレ判断の重要材料。',
    loadContent: loadMd('newzealand/nz-rbnz-overview.md'),
    relatedIndicators: ['nz-ppi', 'nz-pmi'],
    tags: ['ニュージーランド', 'RBNZ', 'OCR', 'MPC', 'Remit', 'インフレ目標', 'デュアルマンデート', '物価安定', '雇用', 'NZD'],
  },

  // --- ニュージーランド / 貿易構造 ---
  {
    indicatorId: 'nz-trade',
    title: '貿易構造（ニュージーランド）',
    country: 'newzealand',
    category: 'economy',
    summary: '中国が最大の輸出先（26.85%）。乳製品・食肉・木材が輸出中核で、機械・燃料は輸入依存。サービス輸出（観光・教育）も重要。中国景気・乳製品価格・木材市況が貿易環境を左右。',
    loadContent: loadMd('newzealand/nz-trade.md'),
    relatedIndicators: ['nz-rbnz-overview', 'nz-pmi', 'trade-balance'],
    tags: ['ニュージーランド', '貿易', '中国', '乳製品', '木材', '食肉', '観光', '教育', 'MFAT', 'Stats NZ', 'NZD'],
  },

  // --- ニュージーランド / 乳製品価格（GDT） ---
  {
    indicatorId: 'nz-global-dairy-trade',
    title: '乳製品価格（GDT）',
    country: 'newzealand',
    category: 'economy',
    summary: 'Global Dairy Trade Eventsの数量加重価格指数。NZ輸出収入とNZDに直結。商品別変化率・平均価格・販売数量・連続性を分けて読み、ヘッドラインだけで判断しない。',
    loadContent: loadMd('newzealand/nz-global-dairy-trade.md'),
    relatedIndicators: ['nz-trade', 'nz-rbnz-overview', 'nz-traded-nontraded'],
    tags: ['ニュージーランド', 'GDT', 'Global Dairy Trade', '乳製品', '全粉乳', '脱脂粉乳', 'バター', 'チーズ', 'WMP', 'SMP', 'Fonterra', 'NZD', '交易条件', '輸出収入', '中国需要', 'オークション'],
  },

  // --- ニュージーランド / 貿易財・非貿易財インフレ ---
  {
    indicatorId: 'traded-nontraded',
    title: '貿易財・非貿易財インフレ（ニュージーランド）',
    country: 'newzealand',
    category: 'inflation',
    summary: '非貿易財は国内の需給・賃金・サービス価格を映す基調的物価圧力。RBNZが国内インフレ圧力の把握で重視。貿易財は為替・国際価格で振れやすい。2025年12月は非貿易3.5%・貿易2.6%。',
    loadContent: loadMd('newzealand/nz-traded-nontraded.md'),
    relatedIndicators: ['nz-rbnz-overview', 'nz-ppi'],
    tags: ['ニュージーランド', '貿易財', '非貿易財', 'Traded', 'Non-tradables', 'CPI', 'RBNZ', 'Stats NZ', '基調インフレ', '国内需給', 'サービス価格', 'NZD'],
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

  // --- オーストラリア / 経済概要・RBA ---
  {
    indicatorId: 'au-rba-overview',
    title: 'オーストラリア経済とRBAの見方',
    country: 'australia',
    category: 'policy',
    summary: 'RBAはCPI 2〜3%レンジのデュアルマンデート。trimmed meanを基調インフレの中心指標として重視。国内はサービス主導、輸出は資源（57%）中心で中国向け30%が最大。',
    loadContent: loadMd('australia/au-rba-overview.md'),
    relatedIndicators: ['au-ppi', 'au-pmi'],
    tags: ['オーストラリア', 'RBA', 'デュアルマンデート', 'CPI', 'trimmed mean', '資源', '鉄鉱石', '石炭', 'LNG', '中国', '豪ドル', 'AUD'],
  },

  // --- オーストラリア / 貿易構造 ---
  {
    indicatorId: 'au-trade',
    title: '貿易構造（オーストラリア）',
    country: 'australia',
    category: 'economy',
    summary: '中国向け輸出比率が約30%で最大。資源輸出の45%が中国向け。鉄鉱石・石炭・LNGが輸出中核だが、教育・観光のサービス輸出も重要。中国景気と資源価格が豪州経済・豪ドルに強く影響。',
    loadContent: loadMd('australia/au-trade.md'),
    relatedIndicators: ['au-rba-overview', 'au-ppi'],
    tags: ['オーストラリア', '貿易', '中国', '鉄鉱石', '石炭', 'LNG', '教育', '観光', '資源', '豪ドル', 'AUD', 'RBA'],
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

  // --- オーストラリア / ANZ求人広告 ---
  {
    indicatorId: 'anz-job-advertisements',
    title: 'ANZ求人広告件数（オーストラリア）',
    country: 'australia',
    category: 'employment',
    summary: '企業の採用意欲を月次で早期に捉える先行指標。失業率に1か月程度先行し逆相関。就業者数・フルタイム雇用とも正相関。ABS Job Vacanciesと相互補完的に使える。',
    loadContent: loadMd('australia/au-anz-job-advertisements.md'),
    relatedIndicators: ['au-rba-overview', 'au-trade'],
    tags: ['オーストラリア', 'ANZ', '求人広告', '失業率', '就業者数', 'フルタイム', 'ABS', 'Job Vacancies', '労働市場', '先行指標', 'AUD'],
  },

  // --- オーストラリア / アンダー・ユーティライゼーション率 ---
  {
    indicatorId: 'underutilization',
    title: 'アンダー・ユーティライゼーション率（オーストラリア）',
    country: 'australia',
    category: 'employment',
    summary: '失業率＋不完全就業率で測る労働力余剰指標。失業率だけでは見えない労働市場の緩み・引き締まりを把握。RBAの完全雇用評価・賃金圧力判断の補助指標。',
    loadContent: loadMd('australia/au-underutilization.md'),
    relatedIndicators: ['anz-job-advertisements', 'au-rba-overview'],
    tags: ['オーストラリア', 'アンダー・ユーティライゼーション', 'Underutilisation', '失業率', '不完全就業率', 'Underemployment', 'ABS', 'RBA', '完全雇用', '労働市場', '賃金圧力', 'volume underutilisation', 'u-series', 'AUD'],
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

  // --- オーストラリア / 家計消費とCPI ---
  {
    indicatorId: 'household-spending',
    title: '家計消費とCPIの関係（オーストラリア）',
    country: 'australia',
    category: 'consumer',
    summary: '家計消費の鈍化はインフレ率低下に1〜2か月先行しやすい。前年比で有効、前月比はノイズ大。trimmed meanはヘッドラインCPIよりさらに遅れて反応。需要主導の物価圧力を見る指標。',
    loadContent: loadMd('australia/au-household-spending-cpi.md'),
    relatedIndicators: ['au-rba-overview', 'household-saving-ratio', 'au-ppi'],
    tags: ['オーストラリア', '家計消費', 'Household Spending', 'CPI', 'trimmed mean', 'インフレ', 'ABS', 'RBA', '需要', '先行指標', 'AUD'],
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

  // --- ユーロ圏 / 伊独スプレッド ---
  {
    indicatorId: 'btp-bund-spread',
    title: '伊独国債利回りスプレッド',
    country: 'eurozone',
    category: 'policy',
    summary: 'BTP-Bundスプレッドはユーロ圏の分断リスクを映す温度計。175-200bpで注意、250bp超でECBの痛みの閾値。スプレッド縮小はユーロ高、拡大はユーロ安に作用しやすい。',
    loadContent: loadMd('eurozone/btp-bund-spread.md'),
    relatedIndicators: ['ecb-rates', 'ecb-policy-framework'],
    tags: ['伊独スプレッド', 'BTP', 'Bund', 'イタリア', 'ドイツ', '国債', 'TPI', 'ユーロ', 'EUR/USD', '分断リスク', '信用リスク'],
  },

  // --- ユーロ圏 / ECB政策枠組み ---
  {
    indicatorId: 'ecb-policy-framework',
    title: 'ECB政策枠組み',
    country: 'eurozone',
    category: 'policy',
    summary: 'ECBの最優先目標は中期的にHICP2％。基調インフレ（HICPX）・賃金・政策伝達を重視。非ユーロ圏中銀との連動性の違いも整理。',
    loadContent: loadMd('eurozone/ecb-policy-framework.md'),
    relatedIndicators: ['ecb-rates', 'ecb-spf', 'ecb-m3'],
    tags: ['ECB', 'HICP', 'HICPX', '基調インフレ', '物価安定', '2％目標', 'デンマーク', 'スウェーデン', 'スイス', 'SNB', 'リクスバンク', 'ユーロ圏'],
  },

  // --- ユーロ圏 / ECB預金ファシリティ金利 ---
  {
    indicatorId: 'ecb-rates',
    title: 'ECB預金ファシリティ金利',
    country: 'eurozone',
    category: 'policy',
    summary: 'ECBの3つの主要金利（預金ファシリティ・主要リファイナンスオペ・限界貸付ファシリティ）の役割と、理事会後の会見・関係者報道の見方。',
    loadContent: loadMd('eurozone/ecb-rates.md'),
    relatedIndicators: ['ecb-m3', 'ecb-spf', 'ez-pmi'],
    tags: ['ECB', '預金ファシリティ', 'リファイナンスオペ', '限界貸付', 'ラガルド', '記者会見', '関係者報道', '利下げ', '金融政策', 'ユーロ圏'],
  },

  // --- ユーロ圏 / 銀行金利（MIR） ---
  {
    indicatorId: 'ecb-bank-interest-rates',
    title: '銀行金利（MIR）',
    country: 'eurozone',
    category: 'policy',
    summary: 'ECBのMFI金利統計（MIR）。企業向け貸出金利・住宅ローン金利を新規取引/残高ベースで把握し、政策金利の銀行貸出への波及を確認する。',
    loadContent: loadMd('eurozone/ecb-bank-interest-rates.md'),
    relatedIndicators: ['ecb-rates', 'ecb-bls', 'ecb-m3', 'ecb-policy-framework'],
    tags: ['MIR', 'MFI金利統計', '銀行金利', 'ECB', '企業向け貸出金利', '住宅ローン金利', 'Composite Cost of Borrowing', '新規取引', '残高ベース', '金融政策', '波及', 'ユーロ圏'],
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

  // --- ユーロ圏 / ECBマクロ経済予測 ---
  {
    indicatorId: 'ecb-macro-projections',
    title: 'ECBマクロ経済予測',
    country: 'eurozone',
    category: 'policy',
    summary: 'ECBスタッフが年4回公表するGDP・HICP・失業率・賃金の見通し。民間消費と外需がGDP見通しの中心要因であり、修正方向が政策金利期待とユーロの方向感に影響しやすい。',
    loadContent: loadMd('eurozone/ecb-macro-projections.md'),
    relatedIndicators: ['ecb-rates', 'ecb-policy-framework', 'ecb-gdp', 'ez-pmi'],
    tags: ['ECB', 'マクロ経済予測', 'GDP', 'HICP', '失業率', '賃金', '民間消費', '外需', 'ユーロ圏', '見通し'],
  },

  // --- ユーロ圏 / GDP ---
  {
    indicatorId: 'ecb-gdp',
    title: 'GDP（ユーロ圏）',
    country: 'eurozone',
    category: 'economy',
    summary: 'Eurostatが四半期公表するユーロ圏GDP。PMI→小売売上・鉱工業生産→GDPの順で景気を確認する流れの最終段階。成長見通しの下方修正はECB緩和観測とユーロ安に作用しやすい。',
    loadContent: loadMd('eurozone/ecb-gdp.md'),
    relatedIndicators: ['ez-pmi', 'ecb-production', 'ecb-retail-trade', 'ecb-macro-projections'],
    tags: ['GDP', 'ユーロ圏', 'Eurostat', '成長率', '景気', '速報値'],
  },

  // --- ユーロ圏 / ドイツとユーロ圏の関係 ---
  {
    indicatorId: 'germany-eurozone-relationship',
    title: 'ドイツ経済とユーロ圏の関係',
    country: 'eurozone',
    category: 'economy',
    summary: 'ドイツはユーロ圏GDPの約4分の1を占める最大経済国。製造業比重が高く、外需・機械設備投資の変動を受けやすい。域外輸出の33.7%・輸入の26.7%を占め、ユーロ圏貿易統計を大きく左右する一方、ユーロ圏全体ではサービス部門の比重も高くドイツ製造業だけでは判断できない。',
    loadContent: loadMd('eurozone/germany-eurozone-relationship.md'),
    relatedIndicators: ['ecb-gdp', 'germany-pmi', 'ez-pmi', 'eu-international-trade', 'ecb-production'],
    tags: ['ドイツ', 'ユーロ圏', '製造業', 'GDP', 'Eurostat', 'Destatis', '輸出', '設備投資', '機械', '自動車', 'サービス', '構造'],
  },

  // --- ユーロ圏 / IFO景況感指数（ドイツ） ---
  {
    indicatorId: 'ifo-business-climate',
    title: 'IFO企業景況感指数（ドイツ）',
    country: 'eurozone',
    category: 'economy',
    summary: 'Ifo研究所が月次公表するドイツ企業景況感指数。約9,000社対象、2015=100の季節調整済指数。総合指数は現状判断と期待の2成分から構成され、期待がGDPに先行しやすい。月次→四半期平均→前期差（ΔĪ_Q）でGDPと比較する使い方が実務的。',
    loadContent: loadMd('eurozone/ifo-business-climate.md'),
    relatedIndicators: ['ecb-gdp', 'germany-pmi', 'ez-pmi', 'germany-eurozone-relationship'],
    tags: ['Ifo', 'IFO', '景況感', 'ドイツ', '企業マインド', '現状判断', '期待', 'GDP', '四半期平均', '先行指標', '製造業', 'サービス業'],
  },

  // --- ユーロ圏 / ZEW景況感指数（ドイツ） ---
  {
    indicatorId: 'zew-economic-sentiment',
    title: 'ZEW景況感指数（ドイツ）',
    country: 'eurozone',
    category: 'economy',
    summary: 'ZEW金融市場調査に基づくドイツ景気期待指数。最大300人規模の金融市場専門家を対象に今後6か月の景気・インフレ・金利・株式・為替の見通しを問う。楽観派比率−悲観派比率で表され、0が中立。Ifoより早く公表され、6か月先の期待を測る点で先行指標として使われやすい。',
    loadContent: loadMd('eurozone/zew-economic-sentiment.md'),
    relatedIndicators: ['ifo-business-climate', 'ecb-gdp', 'germany-pmi', 'germany-eurozone-relationship'],
    tags: ['ZEW', '景況感', 'ドイツ', '金融市場専門家', 'センチメント', '期待', '先行指標', 'Ifo', '6か月先', '金利', '株式', '為替'],
  },

  // --- ユーロ圏 / 製造業新規受注（ドイツ） ---
  {
    indicatorId: 'germany-factory-orders',
    title: '製造業新規受注（ドイツ）',
    country: 'eurozone',
    category: 'economy',
    summary: 'Destatisが月次公表するドイツ製造業の新規受注統計。国内受注は国内需要の流れを示す指標で、設備投資との結び付きは資本財受注の方が直接的。海外受注は輸出の先行～同時指標として相関が高いが、大型受注で振れやすく3か月平均で読むのが実務的。',
    loadContent: loadMd('eurozone/germany-factory-orders.md'),
    relatedIndicators: ['ecb-production', 'germany-pmi', 'eu-international-trade', 'ifo-business-climate', 'germany-eurozone-relationship'],
    tags: ['製造業新規受注', 'Factory Orders', 'ドイツ', 'Destatis', 'Bundesbank', '国内受注', '海外受注', '資本財', '機械設備投資', '輸出', '先行指標'],
  },

  // --- ユーロ圏 / 銀行貸出調査（BLS） ---
  {
    indicatorId: 'ecb-bls',
    title: '銀行貸出調査（ユーロ圏・BLS）',
    country: 'eurozone',
    category: 'economy',
    summary: 'ECBが四半期公表する貸出基準・資金需要のサーベイ。企業向け融資需要DIはGDPにやや先行しやすく、特に見通しDIは景気の底打ちや減速の初期変化を示しやすい。',
    loadContent: loadMd('eurozone/ecb-bls.md'),
    relatedIndicators: ['ecb-gdp', 'ecb-m3', 'ecb-rates', 'ez-pmi'],
    tags: ['BLS', 'ECB', '銀行貸出調査', '資金需要', '貸出基準', '信用環境', 'ユーロ圏', '四半期'],
  },

  // --- ユーロ圏 / 貸出動向（BSI） ---
  {
    indicatorId: 'ecb-adjusted-loans',
    title: '貸出動向（ユーロ圏・BSI）',
    country: 'eurozone',
    category: 'economy',
    summary: 'ECB BSI（金融機関BS統計）の調整済貸出。非金融法人・家計・住宅購入向けの前年比から信用循環を読む。BLS（定性調査）と対をなす実残高ベースの指標。',
    loadContent: loadMd('eurozone/ecb-adjusted-loans.md'),
    relatedIndicators: ['ecb-bls', 'ecb-m3', 'ecb-bank-interest-rates', 'ecb-rates'],
    tags: ['BSI', 'Balance Sheet Items', '調整済貸出', 'Adjusted Loans', 'MFI', '非金融法人', '家計', '住宅購入', '信用供給', '信用循環', 'ECB', 'ユーロ圏', '銀行貸出'],
  },

  // --- ユーロ圏 / 鉱工業生産 ---
  {
    indicatorId: 'ecb-production',
    title: '鉱工業生産（ユーロ圏）',
    country: 'eurozone',
    category: 'economy',
    summary: 'Eurostatが月次公表する製造業中心の実体経済指標。前年比ではGDPと同時性が強く、前月比は変化点をやや早く捉えることがある。',
    loadContent: loadMd('eurozone/ecb-production.md'),
    relatedIndicators: ['ecb-gdp', 'ez-pmi', 'ecb-retail-trade'],
    tags: ['鉱工業生産', 'ユーロ圏', 'Eurostat', '製造業', '実体経済', '月次'],
  },

  // --- ユーロ圏 / 国際貿易 ---
  {
    indicatorId: 'eu-international-trade',
    title: '国際貿易（ユーロ圏）',
    country: 'eurozone',
    category: 'economy',
    summary: 'ユーロ高は域外輸出の逆風だが輸入コスト抑制の二面性を持つ。ドイツは輸出GDP比42%と高く為替感応度が特に高い。実効為替レートと国別輸出構造の確認が重要。',
    loadContent: loadMd('eurozone/eu-international-trade.md'),
    relatedIndicators: ['ecb-gdp', 'ez-pmi', 'germany-pmi', 'ecb-production'],
    tags: ['国際貿易', 'ユーロ圏', 'Eurostat', '輸出', '輸入', 'ユーロ高', 'ドイツ', '実効為替レート', '為替'],
  },

  // --- ユーロ圏 / 小売売上高 ---
  {
    indicatorId: 'ecb-retail-trade',
    title: '小売売上高（ユーロ圏）',
    country: 'eurozone',
    category: 'consumer',
    summary: 'Eurostatが月次公表する家計消費の実体指標。GDPと同四半期に強く連動し、個人消費の強弱を月次で確認する役割が大きい。',
    loadContent: loadMd('eurozone/ecb-retail-trade.md'),
    relatedIndicators: ['ecb-gdp', 'ez-pmi', 'ecb-production'],
    tags: ['小売売上', 'ユーロ圏', 'Eurostat', '消費', '家計', '月次'],
  },

  // --- ユーロ圏 / 失業率 ---
  {
    indicatorId: 'ecb-unemployment-chart',
    title: '失業率（ユーロ圏）',
    country: 'eurozone',
    category: 'employment',
    summary: 'ユーロ圏は雇用保護が厚く、景気悪化→失業率悪化に時間差が生じやすい。labour hoardingや労働時間調整が先行するため、PMI雇用指数や平均労働時間も併せて確認が必要。',
    loadContent: loadMd('eurozone/ecb-unemployment.md'),
    relatedIndicators: ['ez-pmi', 'ecb-gdp', 'ecb-macro-projections'],
    tags: ['失業率', 'ユーロ圏', 'Eurostat', '雇用保護', 'レイオフ', 'labour hoarding', '労働時間', 'PMI雇用指数'],
  },

  // --- ユーロ圏 / 賃金上昇率 ---
  {
    indicatorId: 'eurostat-wages',
    title: '賃金上昇率（ユーロ圏）',
    country: 'eurozone',
    category: 'employment',
    summary: 'ユーロ圏の賃金はインフレに対して数四半期遅れて反応しやすい。CPE・CPH・妥結賃金・Labour Cost Indexなど複数系列の併用が重要。',
    loadContent: loadMd('eurozone/eurostat-wages.md'),
    relatedIndicators: ['ecb-negotiated-wages', 'ecb-unemployment-chart', 'ecb-spf'],
    tags: ['賃金', 'ユーロ圏', 'Eurostat', 'Labour Cost Index', 'CPE', 'CPH', 'インフレ', 'HICP'],
  },

  // --- ユーロ圏 / 交渉妥結賃金 ---
  {
    indicatorId: 'ecb-negotiated-wages',
    title: '交渉妥結賃金（ユーロ圏）',
    country: 'eurozone',
    category: 'employment',
    summary: 'ECBが重視する集団賃金交渉の結果指標。コアHICPに対して数四半期遅行しやすく、real wage catch-upが賃金上昇の持続性を高めやすい。',
    loadContent: loadMd('eurozone/ecb-negotiated-wages.md'),
    relatedIndicators: ['eurostat-wages', 'ecb-spf', 'ecb-unemployment-chart', 'ecb-macro-projections'],
    tags: ['妥結賃金', 'ECB', 'ユーロ圏', '賃金交渉', 'real wage catch-up', 'コアHICP', 'インフレ期待', 'wage tracker'],
  },

  // --- ユーロ圏 / IGメタルとドイツ賃金動向 ---
  {
    indicatorId: 'ig-metall-germany-wages',
    title: 'IGメタルとドイツ賃金動向',
    country: 'eurozone',
    category: 'employment',
    summary: 'IGメタル（約220万人）はドイツ最大級の労組で金属・電機産業の賃金交渉トレンドセッター。パイロット協約として他地域に波及する一方、産業別協約は全体の49%・企業別7%に留まる。協約賃金と実際賃金のwage drift、一時金の有無を併せて確認する必要がある。',
    loadContent: loadMd('eurozone/ig-metall-germany-wages.md'),
    relatedIndicators: ['ecb-negotiated-wages', 'eurostat-wages', 'ecb-spf', 'germany-eurozone-relationship'],
    tags: ['IGメタル', 'IG Metall', 'ドイツ', '賃金', '労働組合', 'パイロット協約', '協約賃金', 'wage drift', '金属', '電機', 'Destatis', 'ECB'],
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

  // --- 中国 / クレジットインパルス ---
  {
    indicatorId: 'cn-credit-impulse',
    title: 'クレジットインパルスの見方（中国）',
    country: 'china',
    category: 'policy',
    summary: '社会融資総量ベースで信用供給の加速・減速をGDP比で測る指標。中国景気の先行指標であり、グローバル製造業PMI・米10年債利回り・日本の景気敏感株に半年〜1年先行しやすい。PMI50割れ局面では政策対応の確認材料。',
    loadContent: loadMd('china/cn-credit-impulse.md'),
    relatedIndicators: ['m1-m2', 'cn-pmi', 'caixin-pmi', 'cn-ppi', 'cn-overview', 'global-manufacturing-pmi'],
    tags: ['クレジットインパルス', 'credit impulse', '中国', '社会融資総量', 'TSF', '信用', 'PBOC', 'PMI', '製造業サイクル', '米10年債', '日経平均', '景気敏感株', '先行指標'],
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

// --- 表示順序定義（サイドバーとページ本文で共有） ---
export const HANDBOOK_COUNTRY_ORDER = [
  'usa',
  'japan',
  'eurozone',
  'uk',
  'china',
  'australia',
  'newzealand',
  'canada',
  'switzerland',
  'global',
  'market',
]

export const HANDBOOK_CATEGORY_ORDER = [
  'policy',
  'economy',
  'consumer',
  'employment',
  'inflation',
  'housing',
  'equities',
  'forex',
  'commodities',
  'energy',
  'cot',
  'flow',
  'rebalance',
  'anomaly',
  'options',
  'correlation',
]

/** ハンドブックエントリーをサイドバーと同じ順序でソート */
export function sortHandbookEntries(entries: HandbookEntry[]): HandbookEntry[] {
  const countryRank = (c: string) => {
    const i = HANDBOOK_COUNTRY_ORDER.indexOf(c)
    return i === -1 ? HANDBOOK_COUNTRY_ORDER.length : i
  }
  const categoryRank = (c: string) => {
    const i = HANDBOOK_CATEGORY_ORDER.indexOf(c)
    return i === -1 ? HANDBOOK_CATEGORY_ORDER.length : i
  }
  // 元のインデックスを保持して安定ソート
  return entries
    .map((entry, idx) => ({ entry, idx }))
    .sort((a, b) => {
      const cd = countryRank(a.entry.country) - countryRank(b.entry.country)
      if (cd !== 0) return cd
      const cat = categoryRank(a.entry.category) - categoryRank(b.entry.category)
      if (cat !== 0) return cat
      return a.idx - b.idx
    })
    .map((x) => x.entry)
}
