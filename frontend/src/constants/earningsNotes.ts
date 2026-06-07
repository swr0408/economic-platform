/**
 * Earnings Notes
 * 銘柄別の決算注目点 + セクター共通の見方 + 共通フレーム
 *
 * Source:
 *   - グローバル大型株の決算注目点リファレンス.docx
 *   - グローバル大型株の決算で市場が本当に見るポイント.docx
 *
 * 対象: noFinancials=true の10社を除く127銘柄
 * - URL/IRリンクは省略 (ページ側に既に表示されている)
 * - recentFact は原典に具体的数値があった銘柄のみ
 * - 日本7銘柄(Advantest/Fast Retailing/Tokyo Electron/SoftBank/Toyota/MUFG/Hitachi)は
 *   原典に記載なし、機関投資家の標準的着眼点で補完
 */

// -----------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------

export type EarningsSectorKey =
  | 'semiconductor'    // 半導体・AIインフラ
  | 'cloud_platform'   // クラウド・プラットフォーム・広告
  | 'bank_payments'    // 銀行・決済・保険
  | 'healthcare'       // 医薬・ヘルスケア
  | 'energy_materials' // エネルギー・資源
  | 'capital_consumer' // 資本財・航空宇宙・自動車・通信・消費

export type EarningsNote = {
  /** 株価を動かす本丸を1行で */
  thesis: string
  /** 注目ポイント (3-5項目) */
  watchPoints: string[]
  /** 優先読了KPIタグ (3-5個) */
  priorityKpis: string[]
  /** 直近四半期の具体的事実 (原典に数値があった銘柄のみ) */
  recentFact?: string
  /** セクター分類 */
  sector: EarningsSectorKey
}

export type SectorNote = {
  title: string
  thesis: string
  keyMetrics: string[]
  description: string
}

export type CommonFramework = {
  intro: string
  pillars: { title: string; body: string }[]
  regions: { us: string; japan: string; europe: string; asia: string }
  macroImpact: string
  checklist: string[]
}

// -----------------------------------------------------------------------
// 銘柄別ノート (127社)
// -----------------------------------------------------------------------

export const TICKER_NOTES: Record<string, EarningsNote> = {
  // ====================== 米国 (27) ======================
  // ---- S tier ----
  NVDA: {
    sector: 'semiconductor',
    thesis: 'ヘッドラインEPSより次四半期売上・粗利ガイドが本丸',
    watchPoints: [
      'Data Center売上の伸びとミックス',
      'Blackwell/ネットワーク構成比',
      '総粗利率の維持',
      '供給制約と在庫水準',
      '対中規制の影響コメント',
    ],
    priorityKpis: ['Data Center', '粗利率', '次Q売上ガイド', '中国規制', '在庫'],
    recentFact: 'Q4 FY26: Data Center売上623億ドル、粗利率75.0%維持',
  },
  AAPL: {
    sector: 'cloud_platform',
    thesis: 'iPhone数量より中国売上・Services粗利・関税コメントが値動きの中心',
    watchPoints: [
      '中国売上の動向',
      'Services粗利率の改善',
      '製品/サービスミックス',
      '為替・関税コメント',
      '自社株買い継続力',
    ],
    priorityKpis: ['iPhone', '中国', 'Services GM', '買戻し', '関税'],
    recentFact: 'Services売上が過去最高、製品ミックス+ドル安で粗利改善',
  },
  MSFT: {
    sector: 'cloud_platform',
    thesis: '上振れより「AI需要に供給が追いつくか」が市場テーマ',
    watchPoints: [
      'Azure成長率',
      '商用RPO (OpenAI含む/除く)',
      'Copilot/AIの収益化',
      'CapExと減価償却',
      '提携先持分損益',
    ],
    priorityKpis: ['Azure', 'RPO', 'AI ARR', 'CapEx', '非GAAP調整'],
    recentFact: 'Q3 FY26 商用RPO 6,270億ドル',
  },
  AMZN: {
    sector: 'cloud_platform',
    thesis: 'AWSとCapExの組み合わせが最重要。投資負担で圧迫されるFCFを見る',
    watchPoints: [
      'AWS成長率と利益率',
      '小売のユニット成長',
      'AI投資の回収',
      'CapExで圧迫されるFCF',
      '一過性の投資評価益ノイズ',
    ],
    priorityKpis: ['AWS', '営業利益率', 'FCF', 'CapEx', '一過性益'],
    recentFact: 'AWS売上376億ドル・営業利益142億ドル、2026年CapEx約2,000億ドル',
  },
  GOOGL: {
    sector: 'cloud_platform',
    thesis: '広告在庫の質とAIが既存利益率を崩さないかが核心',
    watchPoints: [
      'Search売上の伸び',
      'YouTube広告とSubscription',
      'Cloud利益率',
      'AI検索の収益化',
      '配当・自社株買い',
    ],
    priorityKpis: ['Search', 'YouTube', 'Cloud margin', 'TAC', '配当'],
    recentFact: 'Search 600億ドル、YouTube広告+11%、Network広告-4%',
  },
  META: {
    sector: 'cloud_platform',
    thesis: '業績そのものよりAI向け投資負担の増え方が値動きを左右',
    watchPoints: [
      '広告単価と広告表示回数',
      'Reelsの収益化',
      'Reality Labs赤字',
      'CapEx上方修正',
      'FCF耐久力',
    ],
    priorityKpis: ['Ad price', 'Impressions', 'CapEx', 'FCF', 'Reality Labs'],
    recentFact: '平均広告単価+12%、Q1 CapEx 198.4億ドル',
  },
  AVGO: {
    sector: 'semiconductor',
    thesis: 'AI半導体とインフラソフト(VMware)の二本柱が両方伸びるか',
    watchPoints: [
      'AI半導体売上の伸び',
      'カスタムASIC/ネットワークのミックス',
      'VMware統合の進捗',
      'EBITDA率',
      '配当',
    ],
    priorityKpis: ['AI semi', 'Networking', 'VMware', 'EBITDA', '配当'],
    recentFact: 'Q1 FY26 AI売上84億ドル、Q2 AI半導体見通し107億ドル',
  },
  TSLA: {
    sector: 'capital_consumer',
    thesis: '自動車会社かAI/自動運転会社か、見方で反応が分かれる',
    watchPoints: [
      '規制クレジット除きの自動車粗利',
      '値下げと受注',
      'エネルギー貯蔵のミックス',
      'Robotaxi/FSDの進捗',
      '工場CapEx',
    ],
    priorityKpis: ['ex-credit auto GM', 'Deliveries', 'Energy', 'FSD', 'CapEx'],
    recentFact: 'Q1 2026 自動車粗利率21.1%、規制クレジット控除後19.2%',
  },
  'BRK-B': {
    sector: 'bank_payments',
    thesis: 'ヘッドライン純利益より営業利益と資本配分が重要',
    watchPoints: [
      '保険引受とFloat',
      '株式ポートフォリオ評価のノイズ',
      'BNSF・公益の安定性',
      '現金残高',
      '自社株買い',
    ],
    priorityKpis: ['Insurance UW', 'Float', 'Cash', 'Buyback', '非保険子会社'],
  },
  JPM: {
    sector: 'bank_payments',
    thesis: '「利益の質」と「景気の地合い」両方を見る金融株の基準銘柄',
    watchPoints: [
      'NII ex Markets',
      'Card NCO',
      '投資銀行/市場部門',
      'CET1',
      '信用費用',
    ],
    priorityKpis: ['NII ex Markets', 'CET1', 'Credit costs', 'Markets', 'Card NCO'],
    recentFact: 'Q1 2026 NII 254億ドル、NII ex Markets 233億ドル、CET1 14.3%、信用費用25億ドル',
  },

  // ---- A tier ----
  V: {
    sector: 'bank_payments',
    thesis: 'カードネットワークなので貸倒れよりボリュームと単価が重要',
    watchPoints: [
      'Payments Volume',
      'Cross-border Volume',
      'Processed Transactions',
      'Value-added Services',
      '自社株買い',
    ],
    priorityKpis: ['Payments volume', 'Cross-border', 'Processed txns', 'VAS', 'Buyback'],
    recentFact: 'Q2 FY26 株主還元92億ドル、新200億ドル枠、PV+9%/CBV+12%/PT+9%',
  },
  MA: {
    sector: 'bank_payments',
    thesis: '決済ボリュームに加え、付加価値サービスの比率上昇が評価差を生む',
    watchPoints: [
      'Gross Dollar Volume',
      'Cross-border',
      'Switched Transactions',
      'VASの伸び',
      '費用率と買戻し',
    ],
    priorityKpis: ['GDV', 'Cross-border', 'Switched txns', 'VAS', 'Buyback'],
    recentFact: 'Q1 2026 GDV+7%/Cross-border+13%/Switched+9%',
  },
  LLY: {
    sector: 'healthcare',
    thesis: '価格低下でも数量が勝てるかが鍵',
    watchPoints: [
      'Mounjaro/Zepboundの数量と実現価格',
      '供給制約',
      'orforglipronを含むパイプライン',
      '償還環境',
      '通期ガイダンス',
    ],
    priorityKpis: ['Mounjaro', 'Zepbound', '価格vs数量', 'Guidance', 'Pipeline'],
    recentFact: 'Q1 売上+56%(数量ドリブン)、Mounjaro 87億ドル/Zepbound 41億ドル、実現価格は低下',
  },
  XOM: {
    sector: 'energy_materials',
    thesis: '原油価格より「価格変動をまたいでどれだけ現金を残すか」',
    watchPoints: [
      'Guyana/Permianの生産',
      'ダウンストリーム/化学マージン',
      '運転資本込みFCF',
      '買戻し',
      '単位コスト',
    ],
    priorityKpis: ['Upstream volumes', 'Downstream margin', 'FCF', 'Buyback', 'Unit cost'],
  },
  CVX: {
    sector: 'energy_materials',
    thesis: '資産ポートフォリオの入れ替えと生産コストが評価差',
    watchPoints: [
      'Permian成長',
      '主要大型案件の進行',
      '精製/化学マージン',
      'FCF',
      '還元継続力',
    ],
    priorityKpis: ['Permian', 'Major projects', 'FCF', 'Buyback', 'Downstream'],
  },
  BAC: {
    sector: 'bank_payments',
    thesis: '金利低下局面でNIIの下支えがあるかが大きい',
    watchPoints: [
      'NII',
      '預金コスト (Deposit beta)',
      'カード/企業向け与信',
      '市場部門',
      'CET1',
    ],
    priorityKpis: ['NII', 'Deposit beta', 'Credit', 'CET1', 'Markets'],
  },
  GS: {
    sector: 'bank_payments',
    thesis: 'ディーラーが最初に見るのはMarketsとIBの組み合わせ',
    watchPoints: [
      '投資銀行案件残 (IB backlog)',
      'FICC/株式トレーディング',
      'AM/AWMのフィー',
      '費用率',
      '資本還元',
    ],
    priorityKpis: ['IB backlog', 'FICC', 'Equities', 'AWM margin', 'Buyback'],
  },
  WFC: {
    sector: 'bank_payments',
    thesis: '改善ストーリーが続くかを見られやすい',
    watchPoints: [
      'NII',
      '商業不動産・カードの信用費用',
      'コスト削減の進捗',
      '規制対応',
      '還元余力',
    ],
    priorityKpis: ['NII', 'CRE credit', 'Expense saves', 'Regulatory', 'Capital return'],
  },
  MS: {
    sector: 'bank_payments',
    thesis: '株式市場が強い時ほどWealthの質が評価される',
    watchPoints: [
      'Wealth純流入 (NNA)',
      '手数料資産比率',
      'Wealthの税前利益率',
      'IB/Markets',
      'CET1',
    ],
    priorityKpis: ['Net new assets', 'Wealth margin', 'IB', 'Markets', 'CET1'],
  },
  NFLX: {
    sector: 'cloud_platform',
    thesis: '加入者純増より収益単価と広告の伸びが重要に',
    watchPoints: [
      'ARM (Average Revenue per Member)',
      '広告プラン収益化',
      '営業利益率',
      'コンテンツ現金支出',
      'FX',
    ],
    priorityKpis: ['ARM', 'Ad tier', 'Op margin', 'Content cash', 'FX'],
    recentFact: '2026年売上と営業利益率目標を維持',
  },

  // ---- B tier ----
  UNH: {
    sector: 'healthcare',
    thesis: 'ヘルスケアの中では医療コスト率の変化が最も株価に効く',
    watchPoints: [
      'Medical Care Ratio',
      'Medicare/Medicaidの医療利用率',
      'Optum利益率',
      '保険料改定',
      'ガイダンス',
    ],
    priorityKpis: ['MCR', 'Medicare', 'Optum', 'Guidance', 'Pricing'],
    recentFact: 'Medical Care Ratio 83.9%、通期見通しを引き上げ',
  },
  JNJ: {
    sector: 'healthcare',
    thesis: 'ヘルスケア・コングロマリットなので事業別の質を見る必要がある',
    watchPoints: [
      'MedTech手技回復',
      '主力薬の特許/侵食',
      '新薬ミックス',
      '訴訟関連一過性',
      '還元',
    ],
    priorityKpis: ['MedTech', 'Oncology', 'Legal one-offs', 'Guidance', 'Buyback/Div'],
  },
  ABBV: {
    sector: 'healthcare',
    thesis: '主力交代 (Humira→Skyrizi/Rinvoq) の進み方が全て',
    watchPoints: [
      'Humira減収のペース',
      'Skyrizi/Rinvoqの売上',
      '美容・神経の構成比',
      'パイプライン',
      '通期ガイド',
    ],
    priorityKpis: ['Skyrizi', 'Rinvoq', 'Humira erosion', 'Aesthetics', 'Guidance'],
  },
  MRK: {
    sector: 'healthcare',
    thesis: '評価は「Keytruda後」をどこまで見せられるか',
    watchPoints: [
      'Keytruda依存度',
      'Gardasilの地域別需要',
      'Animal Health',
      'LOE対策のパイプライン/M&A',
      '通期ガイド',
    ],
    priorityKpis: ['Keytruda', 'Gardasil', 'Pipeline', 'Animal Health', 'BD'],
  },
  CAT: {
    sector: 'capital_consumer',
    thesis: '景気敏感株だが、価格と在庫の読み違いが一番危険',
    watchPoints: [
      '販売量',
      '価格実現',
      'ディーラー在庫',
      '資源向け需要',
      'FCF・買戻し',
    ],
    priorityKpis: ['Sales volume', 'Price realization', 'Dealer inv.', 'FCF', 'Buyback'],
    recentFact: '価格実現+4.26億ドル+販売数量増、関税コストが逆風',
  },
  GE: {
    sector: 'capital_consumer',
    thesis: '売上よりアフターマーケットの伸びと残高の厚さが重要',
    watchPoints: [
      '受注',
      '商用サービス残高',
      'LEAPのショップ訪問',
      'Defense',
      'FCF',
    ],
    priorityKpis: ['Orders', 'Services backlog', 'LEAP', 'FCF', 'Margin'],
    recentFact: '1Q26 FCF 17億ドル、受注230億ドル',
  },
  RTX: {
    sector: 'capital_consumer',
    thesis: '航空宇宙・防衛の二面性。民需/軍需のミックスが要点',
    watchPoints: [
      'Pratt GTFの改善',
      'Collinsのアフターマーケット',
      'Defense受注',
      'FCFタイミング',
      '還元',
    ],
    priorityKpis: ['GTF', 'Collins aftermarket', 'Defense awards', 'FCF', 'Buyback/Div'],
  },

  // ====================== 日本 (18) ======================
  // 注: 6857/9983/8035/9984/7203/8306/6501 は原典記載なし、機関投資家標準視点で補完
  '6857.T': {
    sector: 'semiconductor',
    thesis: 'AIテスター需要(HBM/SoC)に支えられるが、顧客集中度と通期ガイドの修正幅が鍵',
    watchPoints: [
      'SoCテスター/メモリテスターの売上構成',
      'HBM向け需要の伸び',
      '通期売上・営業利益ガイド修正',
      '主要顧客集中度',
      '受注残・在庫',
    ],
    priorityKpis: ['SoCテスター', 'HBM', '通期ガイド', '受注残', '営業利益率'],
  },
  '9983.T': {
    sector: 'capital_consumer',
    thesis: '国内ユニクロより海外(中華圏・北米・欧州)の既存店成長と粗利の質',
    watchPoints: [
      '海外ユニクロの既存店売上',
      '日本ユニクロのコメント',
      '中国/北米の利益寄与',
      '在庫水準',
      '通期計画の修正',
    ],
    priorityKpis: ['海外UQ', '国内UQ', '既存店', '在庫', '通期計画'],
  },
  '8035.T': {
    sector: 'semiconductor',
    thesis: '受注額・book-to-billと装置ミックス、通期ガイドの修正方向が中心',
    watchPoints: [
      '受注 / book-to-bill',
      'メモリ/ロジック比率',
      'NAND/DRAM/Foundryのミックス',
      '中国比率',
      '通期売上・営業利益ガイド',
    ],
    priorityKpis: ['受注', 'B-to-B', 'メモリ', '中国比率', '通期ガイド'],
  },
  '9984.T': {
    sector: 'capital_consumer',
    thesis: '会計利益よりNAV変動、Arm持分価値、投資先評価益損のノイズを切り分ける',
    watchPoints: [
      'NAV (時価ベース)',
      'Vision Fundの評価損益',
      'Arm持分価値',
      '自社株買い',
      '借入・流動性',
    ],
    priorityKpis: ['NAV', 'Vision Fund', 'Arm', '買戻し', '流動性'],
  },
  '7203.T': {
    sector: 'capital_consumer',
    thesis: '台数より地域・パワートレインミックスと営業利益の数量/原価/為替分解',
    watchPoints: [
      '地域別販売台数(北米/中国/日本)',
      'HV/BEV比率',
      '営業利益の数量・原価・為替分解',
      '通期計画の修正',
      '関税・FX前提',
    ],
    priorityKpis: ['北米台数', 'HV比率', '営業利益分解', 'FX前提', '通期計画'],
  },
  '8306.T': {
    sector: 'bank_payments',
    thesis: '国内NII上昇、政策保有株売却の進捗、Morgan Stanley持分が三本柱',
    watchPoints: [
      '国内NIM',
      '政策保有株売却',
      'Morgan Stanley持分損益',
      'CET1',
      '自社株買い・配当',
    ],
    priorityKpis: ['NIM', '政策株売却', 'MS持分', 'CET1', '買戻し'],
  },
  '6501.T': {
    sector: 'capital_consumer',
    thesis: 'Lumada(IT/デジタル)の伸びとセグメント別Adjusted EBITAの修正',
    watchPoints: [
      'Lumada売上',
      'IT・社会インフラ・建機・自動車のセグメント別',
      'Adjusted EBITA margin',
      '受注 / 受注残',
      '通期見通し修正',
    ],
    priorityKpis: ['Lumada', 'Adj EBITA', '受注残', '通期計画', 'セグメント'],
  },
  '6758.T': {
    sector: 'capital_consumer',
    thesis: '複数事業の合成体なのでセグメント別の利益質を見る',
    watchPoints: [
      'G&NS (ゲーム)',
      'イメージセンサー (I&SS)',
      '音楽/映画',
      '金融/投資の整理',
      '通期計画・買戻し',
    ],
    priorityKpis: ['G&NS', 'Image sensor', 'Music/Pictures', 'Guidance', 'Buyback'],
  },
  '8316.T': {
    sector: 'bank_payments',
    thesis: '邦銀は金利正常化の恩恵と資本政策が最重要',
    watchPoints: [
      '国内NIM',
      '政策保有株売却',
      '信用費用',
      'CET1',
      '還元方針',
    ],
    priorityKpis: ['NIM', 'Credit costs', 'CET1', '政策株売却', '買戻し'],
  },
  '8411.T': {
    sector: 'bank_payments',
    thesis: '国内金利上昇局面の収益改善をどこまで取り込めるかが焦点',
    watchPoints: [
      'NII',
      '手数料収益',
      'Markets/IB',
      'CET1',
      '株主還元',
    ],
    priorityKpis: ['NII', 'Fees', 'Markets', 'CET1', 'Payout'],
  },
  '8058.T': {
    sector: 'energy_materials',
    thesis: '総合商社はポートフォリオの質と還元方針を見る',
    watchPoints: [
      '資源価格感応度',
      'LNG/原料炭',
      '非資源収益',
      '営業CF',
      '買戻し',
    ],
    priorityKpis: ['Resource sens.', 'Non-resource', 'CF', 'Buyback', 'Asset recycling'],
  },
  '7011.T': {
    sector: 'capital_consumer',
    thesis: '重工は売上より受注残と採算見通しの修正が重要',
    watchPoints: [
      '受注 / 受注残',
      'GTCC・防衛・航空宇宙',
      '工事採算',
      'CF',
      '通期計画',
    ],
    priorityKpis: ['Orders', 'Backlog', 'GTCC', 'Defense', 'CF'],
    recentFact: '受注5.0兆円、受注残12.2兆円',
  },
  '4063.T': {
    sector: 'energy_materials',
    thesis: '景気敏感でも事業間の逆相関がある (シリコン↔PVC) のが特徴',
    watchPoints: [
      '半導体シリコンの価格/数量',
      'PVCの市況',
      '電子材料',
      'CapEx',
      '還元',
    ],
    priorityKpis: ['Silicon', 'PVC', 'Electronics', 'CapEx', 'Buyback'],
  },
  '9433.T': {
    sector: 'capital_consumer',
    thesis: '通信は売上より契約単価と解約率が効く',
    watchPoints: [
      'ARPU',
      'Churn (解約率)',
      '金融/決済',
      '法人DX',
      '株主還元',
    ],
    priorityKpis: ['ARPU', 'Churn', 'Finance', 'Enterprise', 'Return'],
    recentFact: 'ARPU上昇と解約率低下のセット改善',
  },
  '6762.T': {
    sector: 'capital_consumer',
    thesis: '部品株なので在庫調整の進み方を読む必要がある',
    watchPoints: [
      '二次電池',
      'センサー',
      '受動部品',
      'AIサーバー向け部品',
      '為替',
    ],
    priorityKpis: ['Battery', 'Sensor', 'Passive', 'FX', 'Margin'],
  },
  '6954.T': {
    sector: 'capital_consumer',
    thesis: '短サイクルの自動化需要を見る代表銘柄',
    watchPoints: [
      '受注',
      'FA/CNC/Robotの地域別需要',
      '中国設備投資',
      '利益率',
      '為替',
    ],
    priorityKpis: ['Orders', 'China', 'Robot', 'CNC', 'Margin'],
  },
  '4519.T': {
    sector: 'healthcare',
    thesis: '自販と提携収益の両方を見る必要がある',
    watchPoints: [
      '主力薬 (Vabysmo/Hemlibra/Enspryng)',
      '海外ロイヤルティ',
      '薬価改定',
      '開発パイプライン',
      '利益率',
    ],
    priorityKpis: ['Flagship', 'Royalties', '薬価', 'Pipeline', 'Margin'],
  },
  '5803.T': {
    sector: 'capital_consumer',
    thesis: 'AIインフラの周辺恩恵株 (光ファイバー/データセンター)',
    watchPoints: [
      '光ファイバー/データセンター',
      '電力/通信ケーブル',
      '受注残',
      '利益率',
      'CapEx',
    ],
    priorityKpis: ['Optical', 'Data center', 'Orders', 'Margin', 'CapEx'],
  },

  // ====================== オランダ (6) ======================
  ASML: {
    sector: 'semiconductor',
    thesis: '受注より「通期レンジが上がるか」の方が値動きに直結',
    watchPoints: [
      'EUV/High-NA出荷',
      'Installed Base Management売上',
      '粗利率',
      'China比率',
      '通期レンジ',
    ],
    priorityKpis: ['EUV', 'High-NA', 'IBM sales', 'GM', 'FY guide'],
    recentFact: 'Q1 売上88億ユーロ・粗利53.0%、通期36-40Bユーロへ引き上げ',
  },
  ING: {
    sector: 'bank_payments',
    thesis: '欧州銀では金利正常化の恩恵持続と資本還元が評価軸',
    watchPoints: ['NII', '住宅ローン利ざや', '手数料', 'CET1', '買戻し'],
    priorityKpis: ['NII', 'Fees', 'Mortgage', 'CET1', 'Buyback'],
  },
  PRX: {
    sector: 'capital_consumer',
    thesis: '持株会社なので実質価値へのディスカウントが常に論点',
    watchPoints: [
      'Eコマースの採算改善',
      'NAVディスカウント',
      '買戻し',
      'Tencent感応度',
      'フード/OLXの赤字縮小',
    ],
    priorityKpis: ['E-comm profit', 'NAV disc.', 'Buyback', 'Tencent', 'Cost'],
  },
  ASM: {
    sector: 'semiconductor',
    thesis: '設備株の中では受注の質が最重要',
    watchPoints: [
      '受注 (Order intake)',
      'ALD需要',
      'Logic/Foundry vs Memoryのバランス',
      'China比率',
      '粗利',
    ],
    priorityKpis: ['Orders', 'ALD', 'Logic vs Memory', 'China', 'GM'],
  },
  ADYEN: {
    sector: 'bank_payments',
    thesis: '高成長でも採用/投資でマージンが崩れないかを見たい',
    watchPoints: [
      'TPV (Total Payment Volume)',
      'ネット収益',
      'Take rate',
      '営業レバレッジ',
      'エンタープライズ案件',
    ],
    priorityKpis: ['TPV', 'Net revenue', 'Take rate', 'Opex', 'Enterprise'],
  },
  AD: {
    sector: 'capital_consumer',
    thesis: 'ディフェンシブでも価格と数量のどちらで伸びたかが大事',
    watchPoints: [
      '既存店売上',
      'オンライン採算',
      '米国食品インフレ',
      '在庫ロス (Shrink)',
      '還元',
    ],
    priorityKpis: ['Comp sales', 'Online margin', 'US inflation', 'Shrink', 'Buyback'],
  },

  // ====================== 英国 (9) ======================
  AZN: {
    sector: 'healthcare',
    thesis: '大型医薬の中では地域別リスクコメントが重要',
    watchPoints: [
      'Oncology/希少疾患の伸び',
      '中国売上',
      '主要試験結果',
      '利益率',
      '特許崖 (LOE)',
    ],
    priorityKpis: ['Oncology', 'China', 'Trials', 'Margin', 'LOE'],
  },
  HSBA: {
    sector: 'bank_payments',
    thesis: 'UKエクスポージャーと地政学起因の引当が要注意',
    watchPoints: [
      'Banking NII',
      'Wealth手数料',
      'ECL (期待信用損失)',
      'CET1',
      '一過性売却益/評価損益',
    ],
    priorityKpis: ['NII', 'Wealth fees', 'ECL', 'CET1', 'One-offs'],
    recentFact: 'Banking NII 約460億ドルへ更新、ECL 45bp、CET1 14.0%',
  },
  SHEL: {
    sector: 'energy_materials',
    thesis: '商品市況より、在庫価格や運転資本でFCFがどれだけぶれるか',
    watchPoints: [
      'CFFO',
      '運転資本影響',
      'LNG/Trading',
      'Net debt',
      '買戻し',
    ],
    priorityKpis: ['CFFO', 'WC', 'LNG', 'Net debt', 'Buyback'],
    recentFact: 'Q1 Adj Earnings 69億ドル、CFFO(WC除き)172億ドル、WC流出112億ドル、30億ドル買戻し',
  },
  ULVR: {
    sector: 'capital_consumer',
    thesis: '消費株は価格だけで伸びても評価されにくい',
    watchPoints: [
      'Organic growthの数量分解',
      '価格',
      '粗利改善',
      'コスト削減',
      'ポートフォリオ再編',
    ],
    priorityKpis: ['Volume', 'Price', 'GM', 'Cost saves', 'Portfolio'],
  },
  RR: {
    sector: 'capital_consumer',
    thesis: '航空機エンジンは新造機よりアフターが利益ドライバー',
    watchPoints: [
      'Civil Aerospaceの飛行時間',
      '長期サービス契約マージン',
      'Power Systems',
      'FCF',
      'バランスシート改善',
    ],
    priorityKpis: ['Flying hours', 'Service margin', 'Power Sys', 'FCF', 'Deleveraging'],
  },
  GSK: {
    sector: 'healthcare',
    thesis: 'ワクチンの季節性と法務ノイズを読み違えやすい',
    watchPoints: [
      'Specialty Medicines',
      'ワクチン需要',
      'HIV',
      '訴訟・引当',
      '配当',
    ],
    priorityKpis: ['Specialty', 'Vaccines', 'HIV', 'Legal', 'Dividend'],
  },
  RIO: {
    sector: 'energy_materials',
    thesis: '資源株では価格より生産・コスト・案件進捗が先',
    watchPoints: [
      '鉄鉱石出荷',
      '銅成長',
      '単位コスト',
      'CapEx',
      '配当/還元',
    ],
    priorityKpis: ['Iron ore', 'Copper', 'Unit cost', 'CapEx', 'Payout'],
  },
  BP: {
    sector: 'energy_materials',
    thesis: '収益水準より資本配分の信認が強く問われる',
    watchPoints: [
      'Upstream/下流/Trading',
      'FCF',
      'Net debt',
      '買戻し継続力',
      '戦略の一貫性',
    ],
    priorityKpis: ['FCF', 'Net debt', 'Buyback', 'Trading', 'Strategy'],
  },
  NG: {
    sector: 'capital_consumer',
    thesis: '公益株なので利益より資本計画が重要',
    watchPoints: [
      '規制資産成長',
      '許容利回り',
      'プロジェクト実行',
      '増資/資本需要',
      '配当カバー',
    ],
    priorityKpis: ['Rate base', 'Allowed return', 'CapEx', 'Equity need', 'Div cover'],
  },

  // ====================== スイス (7) ======================
  ROG: {
    sector: 'healthcare',
    thesis: 'スイス株は為替影響を必ず切り分ける',
    watchPoints: [
      '新薬成長',
      'バイオシミラー侵食',
      'Diagnostics (中国/検査需要)',
      'CER vs 報告ベース差',
      'パイプライン',
    ],
    priorityKpis: ['New drugs', 'Biosim', 'Dx', 'CER vs rep', 'Pipeline'],
    recentFact: 'CER +6%増収だがスイスフラン高で報告ベース減収、Diagnosticsは中国価格改革と低インフル流行が逆風',
  },
  NOVN: {
    sector: 'healthcare',
    thesis: '大型医薬だが「主力薬の集中度」と「次の柱」が焦点',
    watchPoints: [
      'Kisqali/Pluvictoなど主力',
      '利益率',
      '試験結果',
      'ガイダンス',
      '還元',
    ],
    priorityKpis: ['Flagship', 'Margin', 'Pipeline', 'Guidance', 'Buyback'],
  },
  NESN: {
    sector: 'capital_consumer',
    thesis: '価格頼みの成長から数量(RIG)へ戻れるかが大事',
    watchPoints: [
      'Organic growthのRIG/価格分解',
      'Coffee/Petcare/Nutrition',
      'リコール等一過性',
      'FX',
      'マージン',
    ],
    priorityKpis: ['RIG', 'Pricing', 'Coffee', 'Petcare', 'Recall'],
    recentFact: 'Q1 OG +3.5% = RIG +1.2% + 価格 +2.3%',
  },
  UBSG: {
    sector: 'bank_payments',
    thesis: '大型統合の進捗が利益以上に重い',
    watchPoints: [
      'Wealth NNA (Net New Assets)',
      '統合シナジー',
      'NII',
      'CET1',
      '買戻し',
    ],
    priorityKpis: ['Wealth NNA', 'Integration', 'NII', 'CET1', 'Buyback'],
  },
  ABBN: {
    sector: 'capital_consumer',
    thesis: '景気敏感でも短サイクル/長サイクルのミックスを読む必要',
    watchPoints: [
      'Orders',
      'Book-to-bill',
      'Electrification/Automation利益率',
      'データセンター需要',
      '買戻し',
    ],
    priorityKpis: ['Orders', 'B-to-B', 'Margin', 'DC exposure', 'Buyback'],
  },
  ZURN: {
    sector: 'bank_payments',
    thesis: '保険は増収よりアンダーライティングの質',
    watchPoints: [
      'P&C combined ratio',
      'Life remittances',
      'SST/ソルベンシー',
      '自然災害損失',
      '還元',
    ],
    priorityKpis: ['Combined ratio', 'Remittances', 'Solvency', 'Cat losses', 'Return'],
  },
  CFR: {
    sector: 'capital_consumer',
    thesis: '高級品は地域ミックスと在庫の話が最重要',
    watchPoints: [
      'Jewelryの強さ',
      '中国需要',
      'Wholesale/直営比率',
      '在庫',
      '利益率',
    ],
    priorityKpis: ['Jewelry', 'China', 'Channel', 'Inventory', 'Margin'],
  },

  // ====================== ドイツ (9) ======================
  SIE: {
    sector: 'capital_consumer',
    thesis: 'Digital Industriesの底打ち、SI/Mobilityの受注残が焦点',
    watchPoints: [
      'Digital Industries 受注',
      'Smart Infrastructure margin',
      'Mobility受注残',
      'FCF',
      'Book-to-bill',
    ],
    priorityKpis: ['DI orders', 'SI margin', 'Mobility', 'FCF', 'B-to-B'],
    recentFact: 'book-to-bill 1.12、受注残1,200億ユーロ',
  },
  SAP: {
    sector: 'cloud_platform',
    thesis: '契約残と利益転換のバランスが非常に重要',
    watchPoints: [
      'Current cloud backlog',
      'Cloud売上/利益率',
      'S/4移行',
      'FCF',
      '為替',
    ],
    priorityKpis: ['Cloud backlog', 'Cloud margin', 'S/4', 'FCF', 'FX'],
  },
  ALV: {
    sector: 'bank_payments',
    thesis: '保険は増収よりcombined ratioとSolvency II',
    watchPoints: [
      'P&C combined ratio',
      'Life/Health',
      'Asset Management純流出入',
      'Solvency II',
      '還元',
    ],
    priorityKpis: ['Combined ratio', 'Solvency II', 'AM flows', 'Life margin', 'Return'],
    recentFact: 'combined ratio 92.2%、Solvency II 218%',
  },
  ENR: {
    sector: 'capital_consumer',
    thesis: 'AI/送電投資の恩恵を受けやすい',
    watchPoints: [
      'Grid Technologies受注',
      'Gas Services',
      '風力事業の改善',
      'FCF',
      '保証・一過性損失',
    ],
    priorityKpis: ['Grid orders', 'Gas services', 'Wind', 'FCF', 'One-offs'],
  },
  DTE: {
    sector: 'capital_consumer',
    thesis: 'モバイル本体だけでなく持分先(TMUS)の寄与が大きい',
    watchPoints: [
      'T-Mobile USのサービス収入',
      'Postpaid純増',
      '欧州通信',
      'FTTH投資',
      'FCF・配当',
    ],
    priorityKpis: ['TMUS svc rev', 'Postpaid', 'FCF', 'Fiber', 'Dividend'],
  },
  IFX: {
    sector: 'semiconductor',
    thesis: '半導体でもAIより産業循環の色が強い',
    watchPoints: [
      'Automotive需要',
      'Industrial需要',
      '在庫調整',
      '稼働率',
      '粗利率・CapEx',
    ],
    priorityKpis: ['Auto', 'Industrial', 'Inventory', 'Utilization', 'GM'],
  },
  DBK: {
    sector: 'bank_payments',
    thesis: '欧州銀の中でも費用統制が強く問われる',
    watchPoints: [
      '投資銀行収益',
      'NII',
      'コスト/収益比率',
      'CET1',
      '訴訟・レガシー費用',
    ],
    priorityKpis: ['IB', 'NII', 'Cost-income', 'CET1', 'Legal'],
  },
  MUV2: {
    sector: 'bank_payments',
    thesis: '保険・再保険は単一四半期の災害イベントの見極めが大切',
    watchPoints: [
      '再保険料率',
      '自然災害損失',
      '投資利回り',
      'Solvency',
      '通期利益ガイド',
    ],
    priorityKpis: ['Re pricing', 'Cat losses', 'Inv yield', 'Solvency', 'Guidance'],
  },
  RHM: {
    sector: 'capital_consumer',
    thesis: '売上よりバックログと生産能力が先',
    watchPoints: [
      '防衛受注',
      '弾薬/車両のマージン',
      '設備増強',
      'キャッシュ転換',
      '地政学',
    ],
    priorityKpis: ['Order intake', 'Backlog', 'Margin', 'Capacity', 'Cash conv.'],
  },

  // ====================== デンマーク (7) ======================
  'NOVO-B': {
    sector: 'healthcare',
    thesis: '直近は期待値を再度引き上げられるかが鍵',
    watchPoints: [
      'Wegovy/Ozempic数量',
      '米国アクセスと価格',
      '供給',
      '次世代パイプライン',
      'ガイダンス',
    ],
    priorityKpis: ['Wegovy', 'Ozempic', 'Access', 'Guidance', 'Pipeline'],
    recentFact: '糖尿病・肥満領域売上 +33%',
  },
  DSV: {
    sector: 'capital_consumer',
    thesis: '物流株は売上より粗利の質を見る',
    watchPoints: ['粗利/出荷', 'シナジー', 'コスト効率', 'キャッシュ転換', 'M&A統合'],
    priorityKpis: ['Gross profit', 'Volumes', 'Synergies', 'Cash conv.', 'Integration'],
  },
  DANSKE: {
    sector: 'bank_payments',
    thesis: '北欧銀らしく資本政策と貸倒れの安定性が見どころ',
    watchPoints: ['NII', '手数料', '減損', 'CET1', '還元'],
    priorityKpis: ['NII', 'Fees', 'Impairments', 'CET1', 'Distribution'],
  },
  VWS: {
    sector: 'capital_consumer',
    thesis: '風力は売上より案件採算で株価が動く',
    watchPoints: [
      '受注残',
      '価格条項',
      'Serviceマージン',
      '保証費',
      '運転資本',
    ],
    priorityKpis: ['Orders', 'Service margin', 'Warranty', 'WC', 'Pricing'],
  },
  'NZYM-B': {
    sector: 'capital_consumer',
    thesis: '統合後はシナジーの実現速度が評価軸',
    watchPoints: [
      'シナジー',
      'オーガニック成長',
      'Food/Health/Agのミックス',
      'EBIT',
      'キャッシュ転換',
    ],
    priorityKpis: ['Synergy', 'Organic', 'EBIT', 'Cash conv.', 'Mix'],
  },
  GMAB: {
    sector: 'healthcare',
    thesis: 'バイオは売上よりパイプライン価値と費用規律が重要',
    watchPoints: ['ロイヤルティ収入', '共同開発パイプライン', '自社開発の費用', '現金活用', 'ガイダンス'],
    priorityKpis: ['Royalties', 'Pipeline', 'R&D', 'Cash', 'Guidance'],
  },
  'MAERSK-B': {
    sector: 'capital_consumer',
    thesis: '市況より配船・在庫循環とコスト削減の進捗を読む',
    watchPoints: [
      'コンテナ運賃',
      '契約/スポット比率',
      '物流採算',
      'CapEx',
      '還元',
    ],
    priorityKpis: ['Freight rates', 'Contract mix', 'Logistics', 'CapEx', 'Buyback'],
  },

  // ====================== フランス (8) ======================
  SU: {
    sector: 'capital_consumer',
    thesis: 'AI関連で最も実需を映しやすい電機銘柄の一つ',
    watchPoints: [
      'Organic growth',
      'データセンター/電化需要',
      'ソフトウェア事業',
      '利益率',
      'Book-to-bill',
    ],
    priorityKpis: ['Organic', 'DC demand', 'Software', 'Margin', 'B-to-B'],
  },
  MC: {
    sector: 'capital_consumer',
    thesis: '高級品は売上総額より地域ミックスが重要',
    watchPoints: [
      '部門別オーガニック成長',
      '中国/米国需要',
      '在庫',
      '利益率',
      '為替',
    ],
    priorityKpis: ['Organic', 'China', 'US', 'Inventory', 'Margin'],
  },
  TTE: {
    sector: 'energy_materials',
    thesis: '欧州エネルギー大手として、商品価格より資本規律が評価されやすい',
    watchPoints: ['生産量', 'LNG', 'CFFO', '原価', '買戻し'],
    priorityKpis: ['Production', 'LNG', 'CFFO', 'Buyback', 'Break-even'],
  },
  SAF: {
    sector: 'capital_consumer',
    thesis: '航空エンジンはアフター部門の利益レバレッジが大きい',
    watchPoints: [
      'LEAP納入',
      'スペアパーツ',
      'OE/アフター比率',
      'FCF',
      'サプライチェーン',
    ],
    priorityKpis: ['LEAP', 'Spare parts', 'Mix', 'FCF', 'Supply chain'],
  },
  AIR: {
    sector: 'capital_consumer',
    thesis: '引き渡しのタイミングが四半期ブレを大きくする',
    watchPoints: [
      'Deliveries',
      'エンジン供給制約',
      'EBIT/FCFガイド',
      '受注残',
      '運転資本',
    ],
    priorityKpis: ['Deliveries', 'Supply', 'EBIT', 'FCF', 'Backlog'],
    recentFact: '114機引き渡し、ヘッジと納入構成で利益左右',
  },
  SAN: {
    sector: 'healthcare',
    thesis: '大型医薬の中では主力薬集中度と次世代候補が論点',
    watchPoints: [
      'Dupixent成長',
      'ワクチンの季節性',
      'パイプライン',
      '利益率',
      '資本配分',
    ],
    priorityKpis: ['Dupixent', 'Vaccines', 'Pipeline', 'Margin', 'BD'],
  },
  BNP: {
    sector: 'bank_payments',
    thesis: '欧州ユニバーサルバンクの典型で、部門ミックスの安定性が重要',
    watchPoints: ['NII', 'CIB', 'コスト・収益率', 'CET1', '還元'],
    priorityKpis: ['NII', 'CIB', 'Cost-income', 'CET1', 'Return'],
  },
  CS: {
    sector: 'bank_payments',
    thesis: '保険株では増収より損害率・資本の厚みを先に見る',
    watchPoints: ['P&C価格', 'Technical margin', 'Life/Health', 'Solvency II', '還元'],
    priorityKpis: ['P&C pricing', 'Tech margin', 'L&H', 'Solvency II', 'Distribution'],
  },

  // ====================== 台湾 (2) ======================
  TSM: {
    sector: 'semiconductor',
    thesis: 'AIサイクルの中核で、通期レンジが市場全体にも波及',
    watchPoints: [
      'HPC比率',
      '3nm/5nm比率',
      'CoWoSを含む先端実装',
      '2Q売上/粗利ガイド',
      'CapEx',
    ],
    priorityKpis: ['HPC', '3nm+5nm', '2Q guide', 'GM', 'CapEx'],
    recentFact: '1Q26 HPC比率61%・先端ノード比率74%、Q2 売上39.0-40.2Bドル/粗利65.5-67.5%/営業利益56.5-58.5%、通期+30%超成長',
  },
  '2317.TW': {
    sector: 'capital_consumer',
    thesis: '売上規模よりミックス改善が重要',
    watchPoints: [
      'AIサーバー売上',
      'iPhone受託の季節性',
      'クラウド/ネットワーク',
      '海外生産シフト',
      '利益率',
    ],
    priorityKpis: ['AI servers', 'iPhone', 'Cloud/Net', 'Geo mix', 'Margin'],
  },

  // ====================== 韓国 (4) ======================
  '005930.KS': {
    sector: 'semiconductor',
    thesis: 'AI需要が強くても供給制約とASPがセットで重要',
    watchPoints: [
      'HBM/DRAM/NANDの価格と出荷',
      'Foundry改善',
      'DS (Device Solutions) 利益率',
      'CapEx',
      '株主還元',
    ],
    priorityKpis: ['HBM', 'Memory ASP', 'Foundry', 'CapEx', 'Return'],
  },
  '005380.KS': {
    sector: 'capital_consumer',
    thesis: '自動車株では台数より価格維持と奨励金の動きが重要',
    watchPoints: [
      'ASP/ミックス',
      'インセンティブ',
      '米国現地化',
      'EV採算',
      '還元',
    ],
    priorityKpis: ['ASP', 'Incentives', 'US local.', 'EV margin', 'Payout'],
  },
  '105560.KS': {
    sector: 'bank_payments',
    thesis: '韓国金融株は資本政策が株価感応度を高めやすい',
    watchPoints: ['NIM', 'PCL', 'CET1', '証券/保険寄与', '買戻し/消却'],
    priorityKpis: ['NIM', 'PCL', 'CET1', 'Non-bank', 'Buyback'],
  },
  '055550.KS': {
    sector: 'bank_payments',
    thesis: '銀行単体より金融グループ全体の質を見る',
    watchPoints: ['NIM', '信用費用', 'CET1', '非銀行収益', '配当/買戻し'],
    priorityKpis: ['NIM', 'Credit costs', 'CET1', 'Non-bank', 'Distribution'],
  },

  // ====================== 中国・香港 (10) ======================
  '0700.HK': {
    sector: 'cloud_platform',
    thesis: '広告/ゲーム/FinTech/Cloudの四本柱とAI投資・買戻し継続',
    watchPoints: [
      'Marketing Services (広告)',
      '国内外ゲーム',
      'FinTech/Business Services',
      'AI投資の増え方',
      '買戻し継続',
    ],
    priorityKpis: ['Ads', 'Games', 'FinTech/Cloud', 'AI capex', 'Buyback'],
  },
  BABA: {
    sector: 'cloud_platform',
    thesis: 'Taobao/TmallのCMRとCloudのAI収益化が最重要',
    watchPoints: [
      'CMR (Customer Management Revenue)',
      'CloudのAI収益化',
      'Local Services',
      '利益率',
      '買戻し',
    ],
    priorityKpis: ['CMR', 'Cloud AI', 'Local services', 'Margin', 'Buyback'],
  },
  '1810.HK': {
    sector: 'capital_consumer',
    thesis: 'ハード+インターネット+EVのミックスが論点',
    watchPoints: [
      'スマホASP/プレミアム比率',
      'IoT粗利',
      'EV事業の赤字と出荷',
      'Internet Services',
      'ユーザー数',
    ],
    priorityKpis: ['Smartphone ASP', 'IoT GM', 'EV losses', 'Internet', 'Users'],
  },
  PDD: {
    sector: 'cloud_platform',
    thesis: '高成長でも利益の質を疑われやすい',
    watchPoints: [
      'Take rate',
      'Temuの販管費/補助金',
      '商流の質',
      'FCF',
      '規制環境',
    ],
    priorityKpis: ['Take rate', 'Temu subsidy', 'Marketing', 'FCF', 'Regulation'],
  },
  '3690.HK': {
    sector: 'cloud_platform',
    thesis: '中国内需の温度感を見る高頻度指標',
    watchPoints: [
      'Core local commerceの利益率',
      'In-store/Hotel & Travel',
      '新規事業の赤字',
      '配達補助金',
      'マージン',
    ],
    priorityKpis: ['Core LC', 'Hotel/Travel', 'New init.', 'Subsidies', 'Margin'],
  },
  '1211.HK': {
    sector: 'capital_consumer',
    thesis: '自動車・電池・輸出の三つを同時に見る',
    watchPoints: [
      'NEV販売台数',
      'ASP',
      '輸出',
      'バッテリー一体運営',
      'CapEx',
    ],
    priorityKpis: ['NEV volumes', 'ASP', 'Exports', 'Battery', 'CapEx'],
  },
  '0939.HK': {
    sector: 'bank_payments',
    thesis: '中国大手銀は信用費用と配当持続性が中心',
    watchPoints: ['NIM', '手数料', '資産品質', '引当', '配当'],
    priorityKpis: ['NIM', 'Fees', 'AQ', 'Provisions', 'Dividend'],
  },
  '2318.HK': {
    sector: 'bank_payments',
    thesis: '保険と金融持株の複合体として読む必要',
    watchPoints: [
      '新契約価値 (NBV)',
      '保険利益',
      '投資収益',
      '不動産/クレジット含み損',
      'ソルベンシー',
    ],
    priorityKpis: ['NBV', 'Insurance profit', 'Inv income', 'Credit exp.', 'Solvency'],
  },
  '1398.HK': {
    sector: 'bank_payments',
    thesis: '中国メガバンクは成長より資産品質',
    watchPoints: ['NIM', 'NPL', '引当', '配当', 'LGFV関連エクスポージャー'],
    priorityKpis: ['NIM', 'NPL', 'Provisions', 'Dividend', 'LGFV'],
  },
  '3988.HK': {
    sector: 'bank_payments',
    thesis: '対外業務の色が強い点が他行との違い',
    watchPoints: ['為替・貿易金融', 'NIM', '資産品質', '資本', '配当'],
    priorityKpis: ['FX', 'Trade fin.', 'NIM', 'AQ', 'Capital'],
  },

  // ====================== インド (5) ======================
  'HDFCBANK.NS': {
    sector: 'bank_payments',
    thesis: '大型合併後のバランスシート正常化がまだ主要論点',
    watchPoints: ['NIM', '預金成長', 'CASA比率', '資産品質', '費用率'],
    priorityKpis: ['NIM', 'Deposit', 'CASA', 'AQ', 'Opex'],
  },
  'ICICIBANK.NS': {
    sector: 'bank_payments',
    thesis: 'インド銀行株では成長と引当のバランスが見どころ',
    watchPoints: ['NIM', '小売融資成長', '資産品質', '手数料', '資本'],
    priorityKpis: ['NIM', 'Retail loan', 'AQ', 'Fees', 'Capital'],
  },
  'INFY.NS': {
    sector: 'cloud_platform',
    thesis: 'ITサービスは案件受注とガイダンスが最重要',
    watchPoints: ['売上ガイダンス', 'TCV (大型受注)', 'BFSI需要', '利益率', '採用/離職率'],
    priorityKpis: ['Revenue guide', 'TCV', 'BFSI', 'Margin', 'Hiring/Attr'],
  },
  'LT.NS': {
    sector: 'capital_consumer',
    thesis: 'インド設備投資を読む代表銘柄',
    watchPoints: ['受注流入', '採算', '運転資本', 'インフラ案件進捗', 'CapExサイクル'],
    priorityKpis: ['Order inflow', 'Margin', 'WC', 'Execution', 'CapEx'],
  },
  'M&M.NS': {
    sector: 'capital_consumer',
    thesis: '景気と農村需要の両方を見ることができる',
    watchPoints: ['UV (SUV) 需要', 'トラクター需要', 'ミックス', 'EV投資', '資本配分'],
    priorityKpis: ['UV', 'Tractor', 'Margin', 'EV spend', 'Cap. alloc.'],
  },

  // ====================== カナダ (7) ======================
  RY: {
    sector: 'bank_payments',
    thesis: 'カナダ銀行株では信用費用と資本の厚みが優先',
    watchPoints: ['PCL', 'NIM', '資本市場収益', 'Wealth流入', 'CET1'],
    priorityKpis: ['PCL', 'NIM', 'Cap. markets', 'Wealth', 'CET1'],
  },
  TD: {
    sector: 'bank_payments',
    thesis: '通常時より規制コストのノイズを深く読む銘柄',
    watchPoints: [
      'NIM',
      '米国関連の規制・費用',
      '預金流出入',
      'CET1',
      '還元再開の余地',
    ],
    priorityKpis: ['NIM', 'US costs', 'CET1', 'Expense', 'Return'],
  },
  SHOP: {
    sector: 'cloud_platform',
    thesis: '高成長でも決済/物流を含む低粗利部門の比率上昇に注意',
    watchPoints: ['GMV', 'Merchant Solutions比率', 'Take rate', '営業利益率', 'FCF'],
    priorityKpis: ['GMV', 'Merchant Sol.', 'Take rate', 'Op margin', 'FCF'],
  },
  AEM: {
    sector: 'energy_materials',
    thesis: '金価格よりコストと生産安定性の方が四半期反応に効く',
    watchPoints: ['産金量', 'AISC', '埋蔵量', '主要鉱山の進捗', 'FCF・還元'],
    priorityKpis: ['Production', 'AISC', 'Reserves', 'FCF', 'Buyback/Div'],
  },
  ENB: {
    sector: 'energy_materials',
    thesis: '公益・インフラなので利益より分配余力を読む',
    watchPoints: ['規制資産ベース', '案件稼働', 'DCF', 'レバレッジ', '配当カバー'],
    priorityKpis: ['DCF', 'Leverage', 'Rate base', 'Project', 'Dividend'],
  },
  CNQ: {
    sector: 'energy_materials',
    thesis: '景気より原価統制が株価の持続力を決める',
    watchPoints: ['生産量', '単位コスト', '維持CapEx後FCF', '還元方針', 'オイルサンド稼働率'],
    priorityKpis: ['Production', 'Unit cost', 'Sust. capex', 'FCF', 'Buyback'],
  },
  BAM: {
    sector: 'bank_payments',
    thesis: 'IFRS利益より手数料原資の質を追う銘柄',
    watchPoints: [
      'Fee-bearing capital',
      'ファンドレイズ',
      '資産売却益',
      'キャリー',
      'バランスシート',
    ],
    priorityKpis: ['Fee cap.', 'Fundraise', 'Realizations', 'Carry', 'BS'],
  },

  // ====================== オーストラリア (8) ======================
  'BHP.AX': {
    sector: 'energy_materials',
    thesis: '資源大型株では価格よりオペレーション',
    watchPoints: ['鉄鉱石/銅の生産', '単位コスト', 'CapEx', '中国需要', '配当'],
    priorityKpis: ['Iron ore', 'Copper', 'Unit cost', 'CapEx', 'China demand'],
    recentFact: 'FY26生産ガイダンス据え置き',
  },
  'CBA.AX': {
    sector: 'bank_payments',
    thesis: '豪銀は住宅市場の温度感を映す',
    watchPoints: ['NIM', '住宅ローン競争', '不良債権', 'CET1', 'コスト'],
    priorityKpis: ['NIM', 'Mortgage comp.', 'Bad debts', 'CET1', 'Costs'],
  },
  'NAB.AX': {
    sector: 'bank_payments',
    thesis: '豪銀の中では法人貸出の色が相対的に強い',
    watchPoints: ['企業向け融資', 'NIM', '減損', '費用', 'CET1'],
    priorityKpis: ['Business lending', 'NIM', 'Impairments', 'Costs', 'CET1'],
  },
  'WBC.AX': {
    sector: 'bank_payments',
    thesis: '改善ストーリーの速度が重要',
    watchPoints: ['住宅ローン利ざや', 'コスト', '規制・システム対応', 'CET1', '還元'],
    priorityKpis: ['Mortgage margin', 'Costs', 'CET1', 'Regulatory', 'Remediation'],
  },
  'ANZ.AX': {
    sector: 'bank_payments',
    thesis: '豪銀の中ではM&A統合/事業再編の論点も乗る',
    watchPoints: ['NIM', '統合案件', '資産品質', '資本', '還元'],
    priorityKpis: ['NIM', 'Integration', 'AQ', 'Capital', 'Distribution'],
  },
  'MQG.AX': {
    sector: 'bank_payments',
    thesis: '四半期ごとのブレを構造で読む会社',
    watchPoints: [
      'アニュイティ型 vs マーケット型の配分',
      '資産売却益',
      '資本余力',
      'AUM',
      '収益ミックス',
    ],
    priorityKpis: ['Annuity vs market', 'Realizations', 'Capital', 'AUM', 'Mix'],
  },
  'CSL.AX': {
    sector: 'healthcare',
    thesis: '医薬・ワクチン・プラズマの三事業を分けて見る必要',
    watchPoints: ['血漿採取', '粗利率', 'Seqirus季節性', 'R&D', '為替'],
    priorityKpis: ['Plasma', 'GM', 'Seqirus', 'R&D', 'FX'],
  },
  'RIO.AX': {
    sector: 'energy_materials',
    thesis: '英国上場分と中身は同一(鉄鉱石・銅・コスト)',
    watchPoints: ['鉄鉱石出荷', '銅成長', 'CapEx', 'コスト', '配当'],
    priorityKpis: ['Iron ore', 'Copper', 'CapEx', 'Unit cost', 'Payout'],
  },
}

// -----------------------------------------------------------------------
// セクター共通ノート (6セクター)
// -----------------------------------------------------------------------

export const SECTOR_NOTES: Record<EarningsSectorKey, SectorNote> = {
  semiconductor: {
    title: '半導体・AIインフラ',
    thesis: '最終需要よりAI関連売上、製品ミックス、先端ノード/装置の供給制約、ガイダンスが優先',
    keyMetrics: [
      'Data Center売上 / HPC比率',
      '先端ノード比率 (3nm/5nm/EUV/High-NA)',
      'AI networking / custom accelerator',
      '粗利レンジ',
      'CapExの吸収力',
    ],
    description:
      'NVIDIAのData Center、TSMCのHPC比率と先端ノード比率、ASMLの通期売上レンジ、BroadcomのAI半導体/インフラソフト、SamsungのメモリASPとAI需要が代表的な開示。値動きの引き金は「売上成長」より「粗利と次Qガイド」。',
  },
  cloud_platform: {
    title: 'クラウド・プラットフォーム・広告',
    thesis: '売上総額よりクラウドの収益性、広告単価と在庫、契約残高、CapExの回収可能性',
    keyMetrics: [
      'クラウド成長率と利益率',
      'RPO / 契約残',
      '広告単価・広告在庫',
      'CapExの上振れ/下振れ',
      'FCF耐久力',
    ],
    description:
      'MicrosoftのAzureとRPO、AmazonのAWS利益率とCapEx、AlphabetのSearch/YouTube/Subscriptionミックス、Metaの広告単価とCapEx上方修正が焦点。最も嫌われるのは「売上は強いが投資負担だけ急増してFCFが悪化する決算」。',
  },
  bank_payments: {
    title: '銀行・決済・保険',
    thesis: 'NII/NIM、信用費用、資本比率、ボリューム指標、ソルベンシーが本丸',
    keyMetrics: [
      'NII / NIM',
      '信用費用 / ECL',
      'CET1 / Solvency II',
      '決済ボリューム / クロスボーダー',
      '株主還元',
    ],
    description:
      'JPMのNII ex Markets/CET1、HSBCのBanking NII/ECL、Visa/MastercardのPayments Volume/Cross-border/Switched Transactions、Allianzのcombined ratio/Solvency IIが典型。利益が出ていてもNIIの先行きが悪い・信用費用の前提が甘い・CET1が縮む決算は嫌われる。',
  },
  healthcare: {
    title: '医薬・ヘルスケア',
    thesis: 'EPSより主力薬の数量、価格、供給、適応拡大、パイプライン、医療コスト率',
    keyMetrics: [
      '主力薬の数量 vs 価格',
      'パイプライン進捗',
      '適応拡大',
      '医療コスト率 (MCR)',
      'ガイダンス改定',
    ],
    description:
      'Eli LillyのMounjaro/Zepbound数量増と価格低下、Novo NordiskのGLP-1期待値、RocheのCER増収とDiagnostics逆風、UnitedHealthのMedical Care Ratio 83.9%が代表例。見栄えの増収率ではなく、伸びの内訳(価格か数量か、供給制約や制度逆風はないか)が重要。',
  },
  energy_materials: {
    title: 'エネルギー・資源',
    thesis: '市況感ではなく、CFFO、運転資本、株主還元、プロジェクト実行、単位コスト、在庫評価',
    keyMetrics: [
      'CFFO / 運転資本影響',
      '単位コスト',
      'CapEx',
      '生産ガイダンス',
      '配当・買戻し継続力',
    ],
    description:
      'ShellのCFFO(運転資本除き)172億ドルと運転資本流出112億ドル、RelianceのO2C/Digital/Retail三本柱、BHPの生産ガイダンスと単位コスト・品位が代表例。価格変動をまたいでどれだけキャッシュを残せるか、設備投資や買戻しを維持できるかを見る。',
  },
  capital_consumer: {
    title: '資本財・航空宇宙・自動車・通信・消費',
    thesis: 'テーマは分かれるが共通項は受注残、価格実現、在庫、引き渡し、FX、ARPU、数量/価格分解',
    keyMetrics: [
      '受注 / 受注残 / book-to-bill',
      '価格実現と数量',
      'FCF / 運転資本',
      'ARPU / 数量・価格分解',
      'タリフ・FX影響',
    ],
    description:
      'GE Aerospaceの受注230億ドル、Caterpillarの価格実現と関税逆風、Siemensのbook-to-bill 1.12、AirbusのDeliveries、Mitsubishi Heavyの受注残12.2兆円、Teslaの規制クレジット控除後粗利、NestléのRIG/価格分解、LVMHの地域別オーガニックなど多様。',
  },
}

// -----------------------------------------------------------------------
// 共通フレーム (全銘柄横断)
// -----------------------------------------------------------------------

export const COMMON_FRAMEWORK: CommonFramework = {
  intro:
    'グローバル大型株では、株価を最も動かしやすいのは「今期の着地そのもの」ではなく「前提の置き換え」。次四半期と通期のガイダンス、主力事業の需要の質、粗利率と営業利益率の持続性、キャッシュ化の強さ、規制・地政学・資本配分のコメントを優先して読む。',
  pillars: [
    {
      title: '1. ガイダンスの方向',
      body: '最初に見るべきは「会社が先の前提をどう置き換えたか」。TSMCの売上・粗利・営業利益レンジ、ASMLの通期売上見通し、Amazonの全社CapExが具体例。未達か達成かより、レンジ修正の方向が値動きの中心。',
    },
    {
      title: '2. 成長の質',
      body: '売上成長が数量増・値上げ・ミックス改善・為替のどれで実現されたかで評価が変わる。Eli Lillyの「数量ドリブンだが価格は低下」、Nestléの「RIG/価格分解」、Rocheの「CER増収だが報告ベース減収」のように、伸びの内訳を必ず確認する。',
    },
    {
      title: '3. 利益率とキャッシュ化',
      body: '粗利率や営業利益率の改善が、規制クレジット・為替・在庫評価・運転資本で見かけだけ良くなっていないか。Teslaの規制クレジット控除後粗利、Shellの運転資本流出112億ドル、GE AerospaceのFCFのように、PLだけでなく現金化の質を見る。',
    },
    {
      title: '4. バランスシートと資本配分',
      body: '金融株ではCET1・信用費用、非金融株では自社株買い・配当・CapEx・借入余力。JPMのCET1 14.3%、Visaの新200億ドル枠、Metaの198.4億ドルCapExが代表例。利益が強くても資本が薄い・信用費用が膨らむ・投資負担が急増する決算は評価されにくい。',
    },
  ],
  regions: {
    us: '四半期着地より次四半期の成長率レンジ・RPO・CapEx・買戻し余力が中心。MicrosoftのRPO、MetaのCapEx、AmazonのAWS利益率とAI投資、JPMのNII/CET1/信用費用が主要判断材料。ヘッドラインEPSのビートは入口にすぎず、来四半期の前提変更が本体。',
    japan:
      '会社計画の保守性、通期計画の修正、為替前提、受注残、「事業利益」「コア営業利益」の中身が重要。四半期上振れより「通期を上げるかどうか」が値動きに効くことが多い。決算短信 → 説明資料 → 通期見通しの順で読む。',
    europe:
      'オーガニック成長、price/volume分解、book-to-bill、受注残、CER(恒常為替ベース)、combined ratio、Solvency IIなど「運営KPI」の質を強く見る。会計利益の見栄えより運営指標の質が相場を動かす。',
    asia: 'セグメント別の再加速源、CER/定率為替、ARPU・CMR・広告単価、政策・規制の変化を重視。TSMCのHPC比率、AlibabaのCMR、TencentのMarketing Services、ReliのO2C/Digital/Retailのように、売上総額より「どの事業が再加速しているか」を見る方が速い。',
  },
  macroImpact:
    '最もマクロ波及が大きいのはAI投資とデータセンターCapEx (Amazon 2026年約2,000億ドル、Meta Q1 198.4億ドル、Broadcom Q2 AI半導体107億ドル、TSMC通期+30%超、ASML通期36-40Bユーロ)。電力・冷却・ネットワーク・産業機械・設備投資循環・長期金利まで波及する。次に大きいのが金融・決済 (JPMのNII、HSBCのECL、Visa/Mastercardのクロスボーダー = 信用循環・家計支出の高頻度データ)、資源・産業・消費 (Shellの運転資本、BHPの生産、CATの価格実現、NestléのRIG、KDDI/AirtelのARPU = インフレと実需の確認)。',
  checklist: [
    '見出しで通期/次Qガイドを確認',
    '主力事業のKPIだけを抜く',
    '粗利率・営業利益率の増減要因を分解する',
    '営業CF/FCFと運転資本を必ず見る',
    '買戻し・配当・CapExの前提変更を確認する',
    'Q&Aで需要・価格・供給制約・規制トーンを拾う',
  ],
}

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

export function getEarningsNote(ticker: string | undefined): EarningsNote | undefined {
  if (!ticker) return undefined
  return TICKER_NOTES[ticker]
}

export function getSectorNoteByTicker(ticker: string | undefined): SectorNote | undefined {
  const note = getEarningsNote(ticker)
  if (!note) return undefined
  return SECTOR_NOTES[note.sector]
}

export function hasEarningsNote(ticker: string | undefined): boolean {
  if (!ticker) return false
  return ticker in TICKER_NOTES
}
