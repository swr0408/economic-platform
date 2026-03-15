import type { ReactNode } from 'react'
import {
  StockOutlined,
  GoldOutlined,
  ThunderboltOutlined,
  FundOutlined,
  BarChartOutlined,
  DollarOutlined,
} from '@ant-design/icons'

export type MarketIndicatorItem = {
  code: string
  name: string
  symbolIds: string[]
}

export type MarketSubCategoryItem = {
  code: string
  name: string
  indicators: MarketIndicatorItem[]
}

export type MarketCategoryItem = {
  code: string
  name: string
  icon: ReactNode
  color: string
  description: string
  subCategories: MarketSubCategoryItem[]
}

export const MARKET_CATEGORIES_DATA: MarketCategoryItem[] = [
  {
    code: 'equities',
    name: '株式市場',
    icon: <StockOutlined />,
    color: '#3b82f6',
    description: '主要国の株価指数・個別銘柄',
    subCategories: [
      {
        code: 'us-equities',
        name: '米国株',
        indicators: [
          { code: 'sp500', name: 'S&P 500', symbolIds: ['sp500'] },
          { code: 'nasdaq100', name: 'ナスダック100', symbolIds: ['nasdaq100'] },
          { code: 'nasdaq', name: 'ナスダック総合', symbolIds: ['nasdaq'] },
          { code: 'dow', name: 'ダウ平均', symbolIds: ['dow'] },
          { code: 'russell2000', name: 'ラッセル2000', symbolIds: ['russell2000'] },
          { code: 'vix', name: 'VIX（恐怖指数）', symbolIds: ['vix'] },
          { code: 'sox', name: 'SOX（半導体指数）', symbolIds: ['sox'] },
          { code: 'fear-greed', name: 'Fear & Greed Index', symbolIds: [] },
          { code: 'naaim', name: 'NAAIM Exposure Index', symbolIds: [] },
          { code: 'gex-dix', name: 'GEX / DIX', symbolIds: [] },
          { code: 'cboe-pcr', name: 'CBOE Put/Call Ratio', symbolIds: [] },
          { code: 'sp500-valuation', name: 'S&P 500 Valuation', symbolIds: [] },
          { code: 'nasdaq100-valuation', name: 'Nasdaq 100 Valuation', symbolIds: [] },
          { code: 'growth-value-ratio', name: 'Growth/Value レシオ', symbolIds: [] },
          { code: 'sp500-stock-portion', name: 'S&P500 移動平均線上銘柄比率', symbolIds: [] },
          { code: 'cot-sp500', name: 'S&P 500 CFTCポジション動向', symbolIds: [] },
          { code: 'cot-dow', name: 'ダウ CFTCポジション動向', symbolIds: [] },
          { code: 'cot-nasdaq100', name: 'ナスダック100 CFTCポジション動向', symbolIds: [] },
          { code: 'cot-russell2000', name: 'ラッセル2000 CFTCポジション動向', symbolIds: [] },
          { code: 'cot-vix', name: 'VIX CFTCポジション動向', symbolIds: [] },
        ],
      },
      {
        code: 'jp-equities',
        name: '日本株',
        indicators: [
          { code: 'nikkei225', name: '日経平均', symbolIds: ['nikkei225'] },
          { code: 'topix', name: 'TOPIX', symbolIds: ['topix'] },
          { code: 'nikkei-usd', name: '日経平均（ドル建て）', symbolIds: ['nikkei_usd'] },
          { code: 'nikkei225-valuation', name: '日経平均 Valuation', symbolIds: [] },
          { code: 'topix-valuation', name: 'TOPIX Valuation', symbolIds: [] },
          { code: 'nikkei-regression', name: '日経平均回帰モデル', symbolIds: [] },
          { code: 'electronic-components-balance', name: '電子部品出荷在庫バランス', symbolIds: [] },
          { code: 'jpx-pcr', name: 'JPX Put/Call Ratio', symbolIds: [] },
          { code: 'china-m2-nikkei-yoy', name: '中国M2前年比 / 日経平均前年比', symbolIds: [] },
          { code: 'nikkei-double-inverse', name: '日経ダブルインバース 信用残', symbolIds: [] },
          { code: 'jpx-investor-trading', name: '投資部門別売買状況', symbolIds: [] },
          { code: 'advance-decline-ratio', name: '東証プライム 騰落レシオ', symbolIds: [] },
          { code: 'cot-nikkei225', name: '日経225 CFTCポジション動向', symbolIds: [] },
        ],
      },
      {
        code: 'eu-equities',
        name: '欧州株',
        indicators: [
          { code: 'dax', name: 'DAX', symbolIds: ['dax'] },
          { code: 'ftse100', name: 'FTSE 100', symbolIds: ['ftse100'] },
          { code: 'cac40', name: 'CAC 40', symbolIds: ['cac40'] },
          { code: 'eurostoxx50', name: 'EURO STOXX 50', symbolIds: ['eurostoxx50'] },
        ],
      },
      {
        code: 'tw-semiconductor',
        name: '台湾/半導体',
        indicators: [
          { code: 'twii', name: '台湾加権指数', symbolIds: ['twii'] },
          { code: 'tsmc', name: 'TSMC (ADR)', symbolIds: ['tsmc'] },
          { code: 'tsmc-revenue', name: 'TSMC売上高', symbolIds: [] },
        ],
      },
    ],
  },
  {
    code: 'forex',
    name: '為替',
    icon: <DollarOutlined />,
    color: '#10b981',
    description: '主要通貨ペア・通貨インデックス',
    subCategories: [
      {
        code: 'usd-pairs',
        name: 'ドルストレート',
        indicators: [
          { code: 'usdjpy', name: 'USD/JPY', symbolIds: ['usdjpy'] },
          { code: 'cot-usdjpy', name: '円 CFTCポジション動向', symbolIds: [] },
          { code: 'eurusd', name: 'EUR/USD', symbolIds: ['eurusd'] },
          { code: 'cot-eurusd', name: 'ユーロ CFTCポジション動向', symbolIds: [] },
          { code: 'gbpusd', name: 'GBP/USD', symbolIds: ['gbpusd'] },
          { code: 'cot-gbpusd', name: 'ポンド CFTCポジション動向', symbolIds: [] },
          { code: 'audusd', name: 'AUD/USD', symbolIds: ['audusd'] },
          { code: 'cot-audusd', name: '豪ドル CFTCポジション動向', symbolIds: [] },
          { code: 'nzdusd', name: 'NZD/USD', symbolIds: ['nzdusd'] },
          { code: 'cot-nzdusd', name: 'NZドル CFTCポジション動向', symbolIds: [] },
          { code: 'usdcad', name: 'USD/CAD', symbolIds: ['usdcad'] },
          { code: 'cot-usdcad', name: 'カナダドル CFTCポジション動向', symbolIds: [] },
          { code: 'usdchf', name: 'USD/CHF', symbolIds: ['usdchf'] },
          { code: 'cot-usdchf', name: 'スイスフラン CFTCポジション動向', symbolIds: [] },
        ],
      },
      {
        code: 'jpy-crosses',
        name: 'クロス円',
        indicators: [
          { code: 'eurjpy', name: 'EUR/JPY', symbolIds: ['eurjpy'] },
          { code: 'cot-eurjpy', name: 'ユーロ/円 CFTCポジション動向', symbolIds: [] },
          { code: 'gbpjpy', name: 'GBP/JPY', symbolIds: ['gbpjpy'] },
          { code: 'audjpy', name: 'AUD/JPY', symbolIds: ['audjpy'] },
          { code: 'nzdjpy', name: 'NZD/JPY', symbolIds: ['nzdjpy'] },
          { code: 'cadjpy', name: 'CAD/JPY', symbolIds: ['cadjpy'] },
          { code: 'chfjpy', name: 'CHF/JPY', symbolIds: ['chfjpy'] },
        ],
      },
      {
        code: 'eur-crosses',
        name: 'ユーロクロス',
        indicators: [
          { code: 'eurgbp', name: 'EUR/GBP', symbolIds: ['eurgbp'] },
          { code: 'cot-eurgbp', name: 'ユーロ/ポンド CFTCポジション動向', symbolIds: [] },
          { code: 'euraud', name: 'EUR/AUD', symbolIds: ['euraud'] },
          { code: 'eurnzd', name: 'EUR/NZD', symbolIds: ['eurnzd'] },
          { code: 'eurcad', name: 'EUR/CAD', symbolIds: ['eurcad'] },
          { code: 'eurchf', name: 'EUR/CHF', symbolIds: ['eurchf'] },
        ],
      },
      {
        code: 'gbp-crosses',
        name: 'ポンドクロス',
        indicators: [
          { code: 'gbpaud', name: 'GBP/AUD', symbolIds: ['gbpaud'] },
          { code: 'gbpnzd', name: 'GBP/NZD', symbolIds: ['gbpnzd'] },
          { code: 'gbpcad', name: 'GBP/CAD', symbolIds: ['gbpcad'] },
          { code: 'gbpchf', name: 'GBP/CHF', symbolIds: ['gbpchf'] },
        ],
      },
      {
        code: 'other-crosses',
        name: 'その他クロス',
        indicators: [
          { code: 'audnzd', name: 'AUD/NZD', symbolIds: ['audnzd'] },
          { code: 'audcad', name: 'AUD/CAD', symbolIds: ['audcad'] },
          { code: 'audchf', name: 'AUD/CHF', symbolIds: ['audchf'] },
          { code: 'nzdcad', name: 'NZD/CAD', symbolIds: ['nzdcad'] },
          { code: 'nzdchf', name: 'NZD/CHF', symbolIds: ['nzdchf'] },
          { code: 'cadchf', name: 'CAD/CHF', symbolIds: ['cadchf'] },
        ],
      },
      {
        code: 'currency-index',
        name: '通貨インデックス',
        indicators: [
          { code: 'dxy', name: 'ドルインデックス (DXY)', symbolIds: ['dxy'] },
          { code: 'cot-usd-index', name: 'ドルインデックス CFTCポジション動向', symbolIds: [] },
        ],
      },
    ],
  },
  {
    code: 'commodities',
    name: 'コモディティ',
    icon: <GoldOutlined />,
    color: '#f59e0b',
    description: '貴金属・工業用金属の価格動向',
    subCategories: [
      {
        code: 'precious-metals',
        name: '貴金属',
        indicators: [
          { code: 'gold', name: '金（ドル建て）', symbolIds: ['gold'] },
          { code: 'gold-jpy', name: '金（円建て）', symbolIds: ['gold_jpy'] },
          { code: 'gold-etf-holdings', name: '金ETF保有残高', symbolIds: [] },
          { code: 'wgc-gold-etf', name: '金ETFフロー（WGC）', symbolIds: [] },
          { code: 'gold-premium', name: '金プレミアム/ディスカウント', symbolIds: [] },
          { code: 'sge-gold', name: '中国スポット金 Au(T+D)', symbolIds: [] },
          { code: 'china-gold-etf-balance', name: '中国金ETF残高', symbolIds: [] },
          { code: 'cn-gold-reserves', name: '中国人民銀行金準備', symbolIds: [] },
          { code: 'lbma-stock', name: 'LBMA在庫', symbolIds: [] },
          { code: 'comex-gold-inventory', name: 'COMEX金在庫', symbolIds: [] },
          { code: 'cot-gold', name: '金 CFTCポジション動向', symbolIds: [] },
          { code: 'silver', name: '銀', symbolIds: ['silver'] },
          { code: 'silver-etf-holdings', name: '銀ETF残高', symbolIds: [] },
          { code: 'comex-silver-inventory', name: 'COMEX銀在庫', symbolIds: [] },
          { code: 'cot-silver', name: '銀 CFTCポジション動向', symbolIds: [] },
          { code: 'platinum', name: 'プラチナ', symbolIds: ['platinum'] },
        ],
      },
      {
        code: 'industrial-metals',
        name: '工業用金属',
        indicators: [
          { code: 'copper', name: '銅', symbolIds: ['copper'] },
          { code: 'lme-copper-stock', name: 'LME銅在庫', symbolIds: [] },
          { code: 'comex-copper-stock', name: 'COMEX銅在庫', symbolIds: [] },
          { code: 'shfe-copper-stock', name: 'SHFE銅在庫', symbolIds: [] },
          { code: 'cot-copper', name: '銅 CFTCポジション動向', symbolIds: [] },
          { code: 'aluminum', name: 'アルミニウム', symbolIds: ['aluminum'] },
        ],
      },
    ],
  },
  {
    code: 'energy',
    name: 'エネルギー',
    icon: <ThunderboltOutlined />,
    color: '#ef4444',
    description: '原油・天然ガスの価格動向',
    subCategories: [
      {
        code: 'crude-oil',
        name: '原油',
        indicators: [
          { code: 'wti', name: 'WTI原油', symbolIds: ['crude_oil'] },
          { code: 'brent', name: 'ブレント原油', symbolIds: ['brent_oil'] },
          { code: 'api-weekly-crude-oil-inventories', name: 'API週間原油在庫', symbolIds: [] },
          { code: 'weekly-crude-oil-inventories', name: '週間原油在庫', symbolIds: [] },
          { code: 'cushing-inventory', name: 'クッシング在庫', symbolIds: [] },
          { code: 'distillate-fuel-inventories', name: '蒸留燃料在庫', symbolIds: [] },
          { code: 'gasoline-refinery', name: 'ガソリン在庫/製油稼働率', symbolIds: [] },
          { code: 'adjustments', name: '商業在庫調整', symbolIds: [] },
          { code: 'shale-oil-production', name: 'シェールオイル生産量', symbolIds: [] },
          { code: 'crude-oil-net-demand', name: '原油純需要', symbolIds: [] },
          { code: 'crack-spread', name: 'クラックスプレッド', symbolIds: [] },
          { code: 'short-term-energy-outlook', name: '短期エネルギー見通し（原油）', symbolIds: [] },
          { code: 'opec-momr', name: 'OPEC MOMR', symbolIds: [] },
          { code: 'iea-oil-market-report', name: 'IEA Oil Market Report', symbolIds: [] },
          { code: 'rig-count', name: 'リグ稼働数', symbolIds: [] },
          { code: 'cot-crude-oil', name: '原油 CFTCポジション動向', symbolIds: [] },
          { code: 'cot-brent', name: 'ブレント CFTCポジション動向', symbolIds: [] },
        ],
      },
      {
        code: 'natural-gas',
        name: '天然ガス',
        indicators: [
          { code: 'natural-gas', name: '天然ガス (Henry Hub)', symbolIds: ['natural_gas'] },
          { code: 'natural-gas-storage', name: '天然ガス貯蔵量', symbolIds: [] },
          { code: 'natural-gas-trade', name: '天然ガス輸出入', symbolIds: [] },
          { code: 'lng-exports-by-region', name: 'LNG輸出（国別・エリア別）', symbolIds: [] },
          { code: 'steo-natural-gas', name: '短期エネルギー見通し（天然ガス）', symbolIds: [] },
          { code: 'noaa-hdd-cdd', name: 'HDD/CDD & 気温見通し', symbolIds: [] },
          { code: 'eu-natural-gas-storage', name: 'EU天然ガス貯蔵量', symbolIds: [] },
          { code: 'eu-natural-gas-production', name: 'EU天然ガス生産', symbolIds: [] },
          { code: 'roni', name: 'RONI（エルニーニョ/ラニーニャ）', symbolIds: [] },
          { code: 'cot-natural-gas', name: '天然ガス CFTCポジション動向', symbolIds: [] },
        ],
      },
    ],
  },
  {
    code: 'cot',
    name: 'CFTCCFTCポジション動向動向',
    icon: <BarChartOutlined />,
    color: '#8b5cf6',
    description: 'CFTC建玉報告に基づくCFTCポジション動向',
    subCategories: [
      {
        code: 'cot-equities',
        name: '株式指数',
        indicators: [
          { code: 'cot-sp500', name: 'S&P 500', symbolIds: [] },
          { code: 'cot-dow', name: 'ダウ平均', symbolIds: [] },
          { code: 'cot-nasdaq100', name: 'ナスダック100', symbolIds: [] },
          { code: 'cot-russell2000', name: 'ラッセル2000', symbolIds: [] },
          { code: 'cot-nikkei225', name: '日経225', symbolIds: [] },
          { code: 'cot-vix', name: 'VIX', symbolIds: [] },
        ],
      },
      {
        code: 'cot-forex',
        name: '為替',
        indicators: [
          { code: 'cot-usdjpy', name: '米ドル/円', symbolIds: [] },
          { code: 'cot-eurusd', name: 'ユーロ/米ドル', symbolIds: [] },
          { code: 'cot-gbpusd', name: '英ポンド/米ドル', symbolIds: [] },
          { code: 'cot-audusd', name: '豪ドル/米ドル', symbolIds: [] },
          { code: 'cot-nzdusd', name: 'NZドル/米ドル', symbolIds: [] },
          { code: 'cot-usdcad', name: '米ドル/カナダドル', symbolIds: [] },
          { code: 'cot-usdchf', name: '米ドル/スイスフラン', symbolIds: [] },
          { code: 'cot-usd-index', name: 'ドルインデックス', symbolIds: [] },
          { code: 'cot-eurjpy', name: 'ユーロ/円', symbolIds: [] },
          { code: 'cot-eurgbp', name: 'ユーロ/ポンド', symbolIds: [] },
        ],
      },
      {
        code: 'cot-bonds',
        name: '債券',
        indicators: [
          { code: 'cot-us02y', name: '米国2年債', symbolIds: [] },
          { code: 'cot-us10y', name: '米国10年債', symbolIds: [] },
          { code: 'cot-us30y', name: '米国30年債', symbolIds: [] },
        ],
      },
      {
        code: 'cot-commodities',
        name: 'コモディティ',
        indicators: [
          { code: 'cot-gold', name: '金（ゴールド）', symbolIds: [] },
          { code: 'cot-silver', name: '銀（シルバー）', symbolIds: [] },
          { code: 'cot-copper', name: '銅（カッパー）', symbolIds: [] },
        ],
      },
      {
        code: 'cot-energy',
        name: 'エネルギー',
        indicators: [
          { code: 'cot-crude-oil', name: '原油（WTI）', symbolIds: [] },
          { code: 'cot-brent', name: 'ブレント原油', symbolIds: [] },
          { code: 'cot-natural-gas', name: '天然ガス', symbolIds: [] },
        ],
      },
    ],
  },
  {
    code: 'options',
    name: 'オプション',
    icon: <FundOutlined />,
    color: '#06b6d4',
    description: 'オプション市場の情報・指標',
    subCategories: [
      { code: 'equity-options', name: '株式', indicators: [] },
      { code: 'fx-options', name: '為替', indicators: [] },
      { code: 'commodity-options', name: '商品', indicators: [] },
    ],
  },
]

/** カテゴリコードからカテゴリ情報を取得 */
export function getMarketCategory(code: string): MarketCategoryItem | undefined {
  return MARKET_CATEGORIES_DATA.find((c) => c.code === code)
}

/** カテゴリに含まれる全symbolIdsを取得 */
export function getCategorySymbolIds(categoryCode: string): string[] {
  const category = getMarketCategory(categoryCode)
  if (!category) return []
  return category.subCategories.flatMap((sub) =>
    sub.indicators.flatMap((ind) => ind.symbolIds)
  )
}
