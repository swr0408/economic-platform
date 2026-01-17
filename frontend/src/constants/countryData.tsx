import type { ReactNode } from 'react'
import {
  BankOutlined,
  DollarOutlined,
  TeamOutlined,
  RiseOutlined,
  HomeOutlined,
  ShoppingOutlined,
} from '@ant-design/icons'

export type IndicatorItem = {
  code: string
  name: string
}

export type CategoryItem = {
  code: string
  name: string
  icon: ReactNode
  color: string
  indicators: IndicatorItem[]
}

export type CountryItem = {
  code: string
  name: string
  isoCode: string
  categories: CategoryItem[]
}

export const COUNTRIES_DATA: CountryItem[] = [
  {
    code: 'usa',
    name: 'アメリカ',
    isoCode: 'us',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'fed-watch', name: 'Fed Watch' },
          { code: 'term-premium', name: 'タームプレミアム' },
          { code: 'dot-plot', name: 'Dot Plot' },
          { code: 'fomc-projections', name: 'FOMC経済見通し' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp-growth', name: 'GDP成長率' },
          { code: 'gdp-components-growth', name: 'GDP項目別成長率' },
          { code: 'gdp-contributions', name: 'GDP寄与度' },
          { code: 'potential-gdp', name: '潜在成長率' },
          { code: 'bank-lending', name: '銀行貸し出し態度' },
          { code: 'fci', name: 'FCI-G（金融情勢指数）' },
          { code: 'nfci', name: '金融環境指数（NFCI）' },
          { code: 'gdpnow', name: 'GDPNow' },
          { code: 'ism-manufacturing', name: 'ISM製造業景況指数' },
          { code: 'ism-components', name: 'ISM製造業サブインデックス' },
          { code: 'order-inventory-balance', name: 'ISM受注在庫バランス' },
          { code: 'ism-non-manufacturing', name: 'ISM非製造業景況指数' },
          { code: 'ism-non-manufacturing-components', name: 'ISM非製造業サブインデックス' },
          { code: 'sp-pmi-chart', name: 'S&P Global PMI' },
          { code: 'empire-state', name: 'NY連銀製造業景気指数' },
          { code: 'philadelphia-fed', name: 'フィラデルフィア連銀製造業景気指数' },
          { code: 'nfib', name: 'NFIB中小企業楽観指数' },
          { code: 'nfib-capex', name: 'NFIB設備投資計画' },
          { code: 'industrial-production', name: '鉱工業生産' },
          { code: 'capacity-utilization', name: '設備稼働率' },
          { code: 'durable-goods', name: '耐久財受注' },
          { code: 'us-flights', name: '航空機便数' },
          { code: 'tsa-checkpoint', name: '航空機旅客者数' },
          { code: 'opentable', name: 'レストラン予約件数' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
          { code: 'carts', name: 'シカゴ連銀小売指数（CARTS）' },
          { code: 'affinity-spend', name: 'クレジット / デビットカード支出' },
          { code: 'visa-spending', name: 'Visa支出モメンタム指数' },
          { code: 'total-vehicle-sales', name: '自動車販売台数' },
          { code: 'redbook', name: 'レッドブック（前年比）' },
          { code: 'consumer-credit', name: 'クレジットカードローン残高' },
          { code: 'delinquency-rate', name: 'クレジットカードローン延滞率' },
          { code: 'cb-consumer-confidence', name: 'CB消費者信頼感指数' },
          { code: 'michigan-consumer-sentiment', name: 'ミシガン消費者信頼感指数' },
          { code: 'personal-saving-rate', name: '家計貯蓄率' },
          { code: 'personal-income', name: '個人所得' },
          { code: 'disposable-income', name: '可処分所得' },
          { code: 'pce', name: '個人消費支出（PCE）' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
          { code: 'unemployment-by-reason', name: '失業率内訳' },
          { code: 'job-openings-per-unemployed', name: '求人倍率' },
          { code: 'cb-jobs-labor', name: 'CB雇用機会業況判断' },
          { code: 'nonfarm-payrolls', name: '非農業部門雇用者数' },
          { code: 'fullpart-time', name: 'フルタイム / パートタイム雇用者数' },
          { code: 'multiple-jobs-parttime', name: '複数の仕事を持つ人 / 経済的理由によるパートタイム' },
          { code: 'adp-employment', name: 'ADP雇用者数' },
          { code: 'ner-pulse', name: 'ADP雇用者数（NER Pulse）' },
          { code: 'jolts-indeed', name: 'JOLTS求人 / Indeed求人件数' },
          { code: 'jolts-hires-layoffs', name: 'JOLTS採用数 / 解雇数' },
          { code: 'initial-claims', name: '新規失業保険申請件数' },
          { code: 'continued-claims', name: '継続失業保険申請件数' },
          { code: 'challenger-job-cuts', name: 'チャレンジャー人員削減数' },
          { code: 'average-hourly-earnings', name: '平均時給 / 自発的離職率' },
          { code: 'labor-force-participation', name: '労働参加率' },
          { code: 'adp-wage-growth', name: 'ADP賃金上昇率中央値' },
          { code: 'atlanta-fed-wage', name: 'アトランタ連銀賃金トラッカー' },
          { code: 'indeed-wage-tracker', name: 'Indeed賃金トラッカー' },
          { code: 'pce-food-recreation', name: 'PCEデフレーター飲食宿泊・娯楽' },
          { code: 'employment-cost-index', name: '雇用コスト指数' },
          { code: 'unit-labor-cost', name: '単位労働コスト / 労働生産性' },
          { code: 'nfib-compensation', name: 'NFIB人件費 / 雇用計画' },
          { code: 'nfib-compensation-unemployment', name: 'NFIB労働報酬 / 失業率' },
          { code: 'overtime-hours', name: '平均残業時間' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
          { code: 'cpi-categories', name: 'CPI 項目別' },
          { code: 'pce-deflator', name: 'PCEデフレーター' },
          { code: 'housing-indicators', name: 'Zillow家賃指数 / ケースシラー住宅価格指数 / 家賃CPI' },
          { code: 'zillow-rent-cpi', name: 'Zillow家賃指数 / 家賃CPI' },
          { code: 'ppi', name: 'PPI' },
          { code: 'ppi-categories', name: 'PPI PCE関連項目' },
          { code: 'gscpi', name: 'GSCPI' },
          { code: 'inflation-nowcasting', name: 'インフレーションナウキャスティング' },
          { code: 'import-export-price', name: '輸入物価指数 / 輸出物価指数' },
          { code: 'retail-food-services-price', name: 'シカゴ連銀小売物価指数' },
          { code: 'ny-inflation-expectations', name: 'NYインフレ期待' },
          { code: 'michigan-inflation-expectations', name: 'ミシガンインフレ期待' },

        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'mortgage-rates', name: 'フレディ・マック30年固定住宅ローン金利' },
          { code: 'redfin-case-shiller', name: 'Redfin住宅価格中央値 / ケースシラー住宅価格指数' },
          { code: 'new-home-sales', name: '新築住宅販売' },
          { code: 'pending-home-sales', name: '中古住宅販売保留' },
          { code: 'existing-home-sales', name: '中古住宅販売' },
          { code: 'housing-starts', name: '住宅着工件数' },
          { code: 'nahb-hmi', name: 'NAHB住宅市場指数' },
          { code: 'housing-starts-permits', name: '住宅着工件数 / 建設許可件数' },
          { code: 'rental-vacancy-rate', name: '賃貸空室率' },
        ],
      },
    ],
  },
  {
    code: 'japan',
    name: '日本',
    isoCode: 'jp',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'boj-policy-rate-chart', name: '政策金利' },
          { code: 'ois-curve-chart', name: 'OISカーブ' },
          { code: 'boj-meeting-expectations', name: '日銀政策金利期待' },
          { code: 'boj-outlook', name: '経済・物価情勢の展望' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'quarterly-gdp', name: 'GDP成長率' },
          { code: 'gdp-components', name: 'GDP構成要素（前期比）' },
          { code: 'gdp-deflator', name: 'GDPデフレーター' },
          { code: 'potential-growth', name: '潜在成長率（内閣府）' },
          { code: 'boj-potential-growth', name: '潜在成長率（日銀）' },
          { code: 'boj-lending', name: '貸出動向' },
          { code: 'capital-investment', name: '設備投資' },
          { code: 'iip', name: '鉱工業生産' },
          { code: 'iip-forecast', name: '鉱工業生産予測指数' },
          { code: 'capacity-utilization', name: '稼働率指数' },
          { code: 'boj-tankan', name: '日銀短観' },
          { code: 'bsi', name: '法人企業景気予測調査' },
          { code: 'pmi', name: 'PMI' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'consumer-sentiment', name: '消費動向調査（消費者態度指数）' },
          { code: 'boj-cai', name: '消費活動指数（旅行収支調整前）' },
          { code: 'economy-watcher', name: '景気ウォッチャー調査' },
          { code: 'consumption-expenditure', name: '実質消費支出（家計調査）' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'scheduled-wage', name: '所定内給与' },
          { code: 'scheduled-wage-common', name: '所定内給与（共通事業所）' },
          { code: 'employment-type', name: '雇用形態別労働者過不足判断D.I.' },
          { code: 'unemployment', name: '失業率' },
          { code: 'job-offers', name: '有効求人倍率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'national-cpi', name: '全国CPI' },
          { code: 'cpi-categories', name: '全国CPI 10大費目' },
          { code: 'tokyo-cpi', name: '東京CPI' },
          { code: 'sppi', name: '企業向けサービス価格指数（SPPI）' },
          { code: 'cgpi', name: '企業物価指数（CGPI）' },
          { code: 'cgpi-food-agriculture', name: '企業物価指数：飲食料品 / 農林水産物' },
          { code: 'import-export-price', name: '輸入・輸出物価指数' },
          { code: 'pos-uvpi', name: 'POS-UVPI（消費者購買単価指数）' },
          { code: 'gdp-gap', name: 'GDPギャップ（内閣府）' },
          { code: 'boj-gdp-gap', name: 'GDPギャップ（日銀）' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'housing-starts', name: '住宅着工件数' },
        ],
      },
    ],
  },
  {
    code: 'eurozone',
    name: 'ユーロ圏',
    isoCode: 'eu',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'ecb-rates', name: 'ECB預金ファシリティ金利' },
          { code: 'eurex-ois', name: '3ヶ月ユーロSTR先物カーブ' },
          { code: 'ecb-rate-cuts', name: 'ECB利上げ・利下げ期待' },
          { code: 'ecb-macro-projections', name: 'マクロ経済予測' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'ecb-gdp', name: 'GDP' },
          { code: 'ecb-gdp-components', name: 'GDP構成要素' },
          { code: 'ecb-bls', name: '銀行貸出調査' },
          { code: 'ecb-production', name: '鉱工業生産' },
          { code: 'euro-policy-uncertainty', name: '欧州経済政策不確実性指数' },
          { code: 'eurostat-esi', name: 'ESI（ユーロ圏・主要国）' },
          { code: 'pmi', name: 'PMI' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'ecb-retail-trade', name: '小売売上高（ユーロ圏）' },
          { code: 'eurostat-consumer-confidence', name: '消費者信頼感指数（ユーロ圏）' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'ecb-unemployment-chart', name: '失業率（ユーロ圏）' },
          { code: 'ecb-employment', name: '雇用者数変化（ユーロ圏）' },
          { code: 'ecb-labor-productivity', name: '労働生産性（ユーロ圏）' },
          { code: 'ecb-unit-labour-cost', name: '労働コスト指数（ユーロ圏）' },
          { code: 'eurostat-wages', name: '賃金上昇率（ユーロ圏）' },
          { code: 'ecb-negotiated-wages', name: '交渉妥結賃金（ユーロ圏）' },
          { code: 'indeed-euro-wage', name: 'Indeed賃金トラッカー（ユーロ圏）' },
          { code: 'germany-unemployment', name: '失業率（ドイツ）' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'ecb-hicp', name: 'HICP（ユーロ圏）' },
          { code: 'ecb-hicp-breakdown', name: 'HICP 項目別（ユーロ圏）' },
          { code: 'ecb-ppi', name: 'PPI（ユーロ圏）' },
          { code: 'ecb-inflation-expectations', name: 'インフレ期待 / CES（ユーロ圏）' },
          { code: 'ecb-spf', name: 'インフレ期待 / SPF（ユーロ圏）' },
          { code: 'ecb-spf-core', name: 'コアインフレ期待 / SPF（ユーロ圏）' },
          { code: 'germany-cpi', name: 'CPI（ドイツ）' },
          { code: 'germany-ppi', name: 'PPI（ドイツ）' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'hpi', name: '住宅価格指数' },
        ],
      },
    ],
  },
  {
    code: 'uk',
    name: 'イギリス',
    isoCode: 'gb',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'boe-bank-rate', name: 'BOE政策金利' },
          { code: 'boe-mpc-voting', name: 'MPC投票履歴' },
          { code: 'boe-ois-curve', name: 'OISカーブ' },
          { code: 'boe-economic-outlook', name: 'BOE経済見通し' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'pmi', name: 'PMI' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
          { code: 'claimant-count', name: '失業保険申請件数' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
          { code: 'ppi', name: 'PPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'hpi', name: '住宅価格指数' },
        ],
      },
    ],
  },
  {
    code: 'china',
    name: '中国',
    isoCode: 'cn',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'lpr', name: 'LPR' },
          { code: 'rrr', name: '預金準備率' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'pmi', name: 'PMI' },
          { code: 'industrial-production', name: '鉱工業生産' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
          { code: 'ppi', name: 'PPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'hpi', name: '住宅価格' },
        ],
      },
    ],
  },
  {
    code: 'australia',
    name: 'オーストラリア',
    isoCode: 'au',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'rba-statement', name: 'RBA声明' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'trade-balance', name: '貿易収支' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'employment-change', name: '雇用者数変化' },
          { code: 'unemployment', name: '失業率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'building-permits', name: '建設許可' },
        ],
      },
    ],
  },
  {
    code: 'newzealand',
    name: 'ニュージーランド',
    isoCode: 'nz',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'rbnz-statement', name: 'RBNZ声明' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'trade-balance', name: '貿易収支' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'building-permits', name: '建設許可' },
        ],
      },
    ],
  },
  {
    code: 'canada',
    name: 'カナダ',
    isoCode: 'ca',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'boc-statement', name: 'BOC声明' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'trade-balance', name: '貿易収支' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'employment-change', name: '雇用者数変化' },
          { code: 'unemployment', name: '失業率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'building-permits', name: '建設許可' },
          { code: 'hpi', name: '住宅価格指数' },
        ],
      },
    ],
  },
  {
    code: 'switzerland',
    name: 'スイス',
    isoCode: 'ch',
    categories: [
      {
        code: 'policy',
        name: '金融政策',
        icon: <BankOutlined />,
        color: '#1890ff',
        indicators: [
          { code: 'policy-rate', name: '政策金利' },
          { code: 'snb-statement', name: 'SNB声明' },
        ],
      },
      {
        code: 'economy',
        name: '経済',
        icon: <DollarOutlined />,
        color: '#52c41a',
        indicators: [
          { code: 'gdp', name: 'GDP' },
          { code: 'trade-balance', name: '貿易収支' },
        ],
      },
      {
        code: 'consumer',
        name: '消費',
        icon: <ShoppingOutlined />,
        color: '#13c2c2',
        indicators: [
          { code: 'retail-sales', name: '小売売上高' },
        ],
      },
      {
        code: 'employment',
        name: '雇用',
        icon: <TeamOutlined />,
        color: '#faad14',
        indicators: [
          { code: 'unemployment', name: '失業率' },
        ],
      },
      {
        code: 'inflation',
        name: '物価',
        icon: <RiseOutlined />,
        color: '#ff4d4f',
        indicators: [
          { code: 'cpi', name: 'CPI' },
        ],
      },
      {
        code: 'housing',
        name: '住宅',
        icon: <HomeOutlined />,
        color: '#722ed1',
        indicators: [
          { code: 'hpi', name: '住宅価格指数' },
        ],
      },
    ],
  },
]
