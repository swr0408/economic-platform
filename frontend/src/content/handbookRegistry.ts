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
    summary: 'NY Fedが推計する長期債保有の追加リスク補償。長期金利上昇が景気期待か需給・財政要因かを切り分ける指標。',
    loadContent: loadMd('usa/term-premium.md'),
    relatedIndicators: ['us-interest-rate-spread', 'us-treasury-yields', 'policy-rate'],
    tags: ['タームプレミアム', 'NY Fed', '長期金利', '実質金利', 'QT', '国債', '需給', '財政'],
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
    summary: '全米の製造業購買担当者へのアンケート調査。50を境に景気拡大・後退を判断する先行指標。',
    loadContent: loadMd('usa/ism-manufacturing.md'),
    relatedIndicators: ['ism-components', 'order-inventory-balance', 'sp-pmi-chart', 'cot-crude-oil', 'global-manufacturing-pmi'],
    tags: ['ISM', 'PMI', '製造業', '景気先行指標'],
  },
  {
    indicatorId: 'ism-non-manufacturing',
    title: 'ISM非製造業景況指数',
    country: 'usa',
    category: 'economy',
    summary: 'サービス業を中心とした非製造業の景況感。米国GDPの約8割を占めるサービスセクターの動向を把握。',
    loadContent: loadMd('usa/ism-non-manufacturing.md'),
    relatedIndicators: ['ism-non-manufacturing-components', 'sp-pmi-chart'],
    tags: ['ISM', 'PMI', 'サービス業', '非製造業'],
  },

  // --- USA / 雇用 ---
  {
    indicatorId: 'nonfarm-payrolls',
    title: '非農業部門雇用者数（NFP）',
    country: 'usa',
    category: 'employment',
    summary: '毎月第一金曜発表。労働市場の健全性を示す最重要指標で、マーケットへの影響は極めて大きい。',
    loadContent: loadMd('usa/nonfarm-payrolls.md'),
    relatedIndicators: ['unemployment', 'adp-employment', 'initial-claims'],
    tags: ['NFP', '雇用統計', 'BLS', '労働市場'],
  },

  // --- USA / 物価 ---
  {
    indicatorId: 'cpi',
    title: 'CPI（消費者物価指数）',
    country: 'usa',
    category: 'inflation',
    summary: '消費者が購入する財・サービスの価格変動を測定。FRBの金融政策判断に直結する重要指標。',
    loadContent: loadMd('usa/cpi.md'),
    relatedIndicators: ['pce-deflator', 'ppi', 'median-cpi'],
    tags: ['CPI', 'インフレ', 'BLS', '物価'],
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
    summary: '内閣府が四半期ごとに発表する国内総生産の成長率。速報値と改定値がある。',
    loadContent: loadMd('japan/gdp-growth.md'),
    relatedIndicators: ['gdp-components', 'gdp-deflator'],
    tags: ['GDP', '内閣府', '景気'],
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
    relatedIndicators: ['cot-usdjpy', 'cot-usd-index', 'flow-knowledge', 'rebalance'],
    tags: ['円', 'JPY', '安全資産', 'リスクオフ', '年度末', 'レパトリ', '原油', '交易条件', '日米金利差'],
  },

  // --- マーケット / ドル円 ---
  {
    indicatorId: 'cot-usdjpy',
    title: 'ドル円（USD/JPY）の見方',
    country: 'market',
    category: 'forex',
    summary: '仲値・五十日フロー、日米金利差、米国債利回りとの関係、キャリートレード巻き戻しなど、ドル円を見るための実務的な整理。',
    loadContent: loadMd('market/usdjpy.md'),
    relatedIndicators: ['jpy', 'cot-usd-index', 'cftc-positioning', 'us-interest-rate-spread', 'flow-knowledge'],
    tags: ['ドル円', 'USD/JPY', 'USDJPY', '仲値', '五十日', '日米金利差', 'キャリートレード', '円安', '円高', '為替'],
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
    summary: 'EPS、PER、株式益利回りの定義と実務的な使い方。株価をEPS要因とPER要因に分解する見方。',
    loadContent: loadMd('market/eps-per-earnings-yield.md'),
    relatedIndicators: ['nikkei-225', 'topix'],
    tags: ['EPS', 'PER', '益利回り', 'バリュエーション', '株式', 'イールドスプレッド'],
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
