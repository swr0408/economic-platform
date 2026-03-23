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
          { code: 'vix-term-structure', name: 'VIX期間構造', symbolIds: [] },
          { code: 'historical-volatility', name: 'インプライドボラプレミアム', symbolIds: [] },
          { code: 'vix-cross-ratio', name: 'VIXクロスレシオ', symbolIds: [] },
          { code: 'sector-ratio', name: 'セクターレシオ', symbolIds: [] },
          { code: 'sox', name: 'SOX（半導体指数）', symbolIds: ['sox'] },
          { code: 'fear-greed', name: 'Fear & Greed Index', symbolIds: [] },
          { code: 'naaim', name: 'NAAIM Exposure Index', symbolIds: [] },
          { code: 'gex-dix', name: 'GEX / DIX', symbolIds: [] },
          { code: 'cboe-pcr', name: 'CBOE Put/Call Ratio', symbolIds: [] },
          { code: 'sp500-valuation', name: 'S&P 500 Valuation', symbolIds: [] },
          { code: 'nasdaq100-valuation', name: 'Nasdaq 100 Valuation', symbolIds: [] },
          { code: 'growth-value-ratio', name: 'Growth/Value レシオ', symbolIds: [] },
          { code: 'russell2000-russell1000', name: 'Russell 2000/1000 レシオ', symbolIds: [] },
          { code: 'financial-stress-index', name: '金融ストレス指数（STLFSI4）', symbolIds: [] },
          { code: 'cmdi', name: '企業債券市場ディストレス指数（CMDI）', symbolIds: [] },
          { code: 'us-interest-rate-spread', name: '米国長短金利差', symbolIds: [] },
          { code: 'sp500-stock-portion', name: 'S&P500 移動平均線上銘柄比率', symbolIds: [] },
          { code: 'cot-sp500', name: 'S&P 500 CFTCポジション動向', symbolIds: [] },
          { code: 'cot-dow', name: 'ダウ CFTCポジション動向', symbolIds: [] },
          { code: 'cot-nasdaq100', name: 'ナスダック100 CFTCポジション動向', symbolIds: [] },
          { code: 'cot-russell2000', name: 'ラッセル2000 CFTCポジション動向', symbolIds: [] },
          { code: 'cot-vix', name: 'VIX CFTCポジション動向', symbolIds: [] },
          { code: 'sq-analysis', name: 'SQ/MSQ 検証分析', symbolIds: [] },
        ],
      },
      {
        code: 'jp-equities',
        name: '日本株',
        indicators: [
          { code: 'nikkei225-valuation', name: '日経平均 Valuation', symbolIds: [] },
          { code: 'topix-valuation', name: 'TOPIX Valuation', symbolIds: [] },
          { code: 'nikkei-regression', name: '日経平均回帰モデル', symbolIds: [] },
          { code: 'electronic-components-balance', name: '電子部品出荷在庫バランス', symbolIds: [] },
          { code: 'jpx-pcr', name: 'JPX Put/Call Ratio', symbolIds: [] },
          { code: 'china-m2-nikkei-yoy', name: '中国M2前年比 / 日経平均前年比', symbolIds: [] },
          { code: 'nikkei-double-inverse', name: '日経ダブルインバース 信用残', symbolIds: [] },
          { code: 'jpx-investor-trading', name: '投資部門別売買状況', symbolIds: [] },
          { code: 'mof-securities-trading', name: '対外対内証券売買', symbolIds: [] },
          { code: 'advance-decline-ratio', name: '東証プライム 騰落レシオ', symbolIds: [] },
          { code: 'nt-magnification', name: 'NT倍率', symbolIds: [] },
          { code: 'cot-nikkei225', name: '日経225 CFTCポジション動向', symbolIds: [] },
        ],
      },
      // eu-equities: 現在非表示
      {
        code: 'tw-semiconductor',
        name: '台湾/半導体',
        indicators: [
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
          { code: 'cot-usdjpy', name: '円 CFTCポジション動向', symbolIds: [] },
          { code: 'cot-eurusd', name: 'ユーロ CFTCポジション動向', symbolIds: [] },
          { code: 'cot-gbpusd', name: 'ポンド CFTCポジション動向', symbolIds: [] },
          { code: 'cot-audusd', name: '豪ドル CFTCポジション動向', symbolIds: [] },
          { code: 'cot-nzdusd', name: 'NZドル CFTCポジション動向', symbolIds: [] },
          { code: 'cot-usdcad', name: 'カナダドル CFTCポジション動向', symbolIds: [] },
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
      // gbp-crosses: 現在非表示（CFTC無し）
      // other-crosses: 現在非表示（CFTC無し）
      {
        code: 'currency-index',
        name: '通貨インデックス',
        indicators: [
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
          { code: 'gold-etf-holdings', name: '金ETF保有残高', symbolIds: [] },
          { code: 'wgc-gold-etf', name: '金ETFフロー（WGC）', symbolIds: [] },
          { code: 'gold-premium', name: '金プレミアム/ディスカウント', symbolIds: [] },
          { code: 'sge-gold', name: '中国スポット金 Au(T+D)', symbolIds: [] },
          { code: 'china-gold-etf-balance', name: '中国金ETF残高', symbolIds: [] },
          { code: 'cn-gold-reserves', name: '中国人民銀行金準備', symbolIds: [] },
          { code: 'lbma-stock', name: 'LBMA在庫', symbolIds: [] },
          { code: 'comex-gold-inventory', name: 'COMEX金在庫', symbolIds: [] },
          { code: 'cot-gold', name: '金 CFTCポジション動向', symbolIds: [] },
          { code: 'silver-etf-holdings', name: '銀ETF残高', symbolIds: [] },
          { code: 'comex-silver-inventory', name: 'COMEX銀在庫', symbolIds: [] },
          { code: 'cot-silver', name: '銀 CFTCポジション動向', symbolIds: [] },
        ],
      },
      {
        code: 'industrial-metals',
        name: '工業用金属',
        indicators: [
          { code: 'lme-copper-stock', name: 'LME銅在庫', symbolIds: [] },
          { code: 'comex-copper-stock', name: 'COMEX銅在庫', symbolIds: [] },
          { code: 'shfe-copper-stock', name: 'SHFE銅在庫', symbolIds: [] },
          { code: 'cot-copper', name: '銅 CFTCポジション動向', symbolIds: [] },
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
    name: 'CFTCポジション動向',
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
      {
        code: 'equity-options',
        name: '株式オプション',
        indicators: [
          { code: 'nikkei225-options', name: '日経225オプション', symbolIds: [] },
        ],
      },
      {
        code: 'fx-options',
        name: '為替オプション',
        indicators: [
          { code: 'forex-iv', name: '為替IV', symbolIds: [] },
          { code: 'ny-option-cut', name: 'NYオプションカット', symbolIds: [] },
        ],
      },
      { code: 'commodity-options', name: '商品オプション', indicators: [] },
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

/** サブカテゴリコードからサブカテゴリ情報を取得 */
export function getMarketSubCategory(
  categoryCode: string,
  subCategoryCode: string,
): MarketSubCategoryItem | undefined {
  const category = getMarketCategory(categoryCode)
  if (!category) return undefined
  return category.subCategories.find((s) => s.code === subCategoryCode)
}

/** カテゴリの最初のサブカテゴリコードを取得 */
export function getFirstSubCategoryCode(categoryCode: string): string | undefined {
  const category = getMarketCategory(categoryCode)
  if (!category || category.subCategories.length === 0) return undefined
  return category.subCategories[0].code
}
