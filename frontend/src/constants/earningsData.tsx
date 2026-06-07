import type { ReactNode } from 'react'
import { CalendarOutlined, BarChartOutlined } from '@ant-design/icons'

// -----------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------

export type EarningsTier = 'S' | 'A' | 'B'

export type EarningsCompany = {
  ticker: string       // 表示ティッカー (e.g. "6857.T", "BHP.AX")
  name: string         // 表示名
  tier: EarningsTier
  /** true: FMP free tier に ADR/OTC 相当銘柄が存在しないため財務データ非対応 */
  noFinancials?: boolean
}

export type EarningsCountryItem = {
  code: string
  name: string
  nameJa: string
  flag: string
  color: string
  companies: EarningsCompany[]
}

export type EarningsCategoryItem = {
  code: string
  name: string
  nameJa: string
  icon: ReactNode
  color: string
  description: string
}

// -----------------------------------------------------------------------
// Companies by country
// -----------------------------------------------------------------------

const USA_COMPANIES: EarningsCompany[] = [
  // S
  { ticker: 'NVDA',  name: 'NVIDIA',             tier: 'S' },
  { ticker: 'AAPL',  name: 'Apple',              tier: 'S' },
  { ticker: 'MSFT',  name: 'Microsoft',          tier: 'S' },
  { ticker: 'AMZN',  name: 'Amazon',             tier: 'S' },
  { ticker: 'GOOGL', name: 'Alphabet',           tier: 'S' },
  { ticker: 'META',  name: 'Meta',               tier: 'S' },
  { ticker: 'AVGO',  name: 'Broadcom',           tier: 'S' },
  { ticker: 'TSLA',  name: 'Tesla',              tier: 'S' },
  { ticker: 'BRK-B', name: 'Berkshire Hathaway', tier: 'S' },
  { ticker: 'JPM',   name: 'JPMorgan Chase',     tier: 'S' },
  // A
  { ticker: 'V',     name: 'Visa',               tier: 'A' },
  { ticker: 'MA',    name: 'Mastercard',         tier: 'A' },
  { ticker: 'LLY',   name: 'Eli Lilly',          tier: 'A' },
  { ticker: 'XOM',   name: 'Exxon Mobil',        tier: 'A' },
  { ticker: 'CVX',   name: 'Chevron',            tier: 'A' },
  { ticker: 'BAC',   name: 'Bank of America',    tier: 'A' },
  { ticker: 'GS',    name: 'Goldman Sachs',      tier: 'A' },
  { ticker: 'WFC',   name: 'Wells Fargo',        tier: 'A' },
  { ticker: 'MS',    name: 'Morgan Stanley',     tier: 'A' },
  { ticker: 'NFLX',  name: 'Netflix',            tier: 'A' },
  // B
  { ticker: 'UNH',   name: 'UnitedHealth',       tier: 'B' },
  { ticker: 'JNJ',   name: 'Johnson & Johnson',  tier: 'B' },
  { ticker: 'ABBV',  name: 'AbbVie',             tier: 'B' },
  { ticker: 'MRK',   name: 'Merck',              tier: 'B' },
  { ticker: 'CAT',   name: 'Caterpillar',        tier: 'B' },
  { ticker: 'GE',    name: 'GE Aerospace',       tier: 'B' },
  { ticker: 'RTX',   name: 'RTX',                tier: 'B' },
]

const JAPAN_COMPANIES: EarningsCompany[] = [
  // S
  { ticker: '6857.T',  name: 'Advantest',         tier: 'S' },
  { ticker: '9983.T',  name: 'Fast Retailing',    tier: 'S' },
  { ticker: '8035.T',  name: 'Tokyo Electron',    tier: 'S' },
  { ticker: '9984.T',  name: 'SoftBank Group',    tier: 'S' },
  { ticker: '7203.T',  name: 'Toyota',            tier: 'S' },
  { ticker: '8306.T',  name: 'Mitsubishi UFJ',    tier: 'S' },
  // A
  { ticker: '6501.T',  name: 'Hitachi',           tier: 'A' },
  { ticker: '6758.T',  name: 'Sony',              tier: 'A' },
  { ticker: '8316.T',  name: 'SMFG',              tier: 'A' },
  { ticker: '8411.T',  name: 'Mizuho',            tier: 'A' },
  { ticker: '8058.T',  name: 'Mitsubishi Corp',   tier: 'A' },
  { ticker: '7011.T',  name: 'Mitsubishi Heavy',  tier: 'A' },
  { ticker: '4063.T',  name: 'Shin-Etsu Chemical',tier: 'A' },
  { ticker: '9433.T',  name: 'KDDI',              tier: 'A' },
  { ticker: '6762.T',  name: 'TDK',               tier: 'A' },
  { ticker: '6954.T',  name: 'FANUC',             tier: 'A' },
  { ticker: '4519.T',  name: 'Chugai',            tier: 'A' },
  // B
  { ticker: '5803.T',  name: 'Fujikura',          tier: 'B' },
]

const NETHERLANDS_COMPANIES: EarningsCompany[] = [
  { ticker: 'ASML',    name: 'ASML',              tier: 'S' },
  { ticker: 'ING',     name: 'ING',               tier: 'A' },
  { ticker: 'PRX',     name: 'Prosus',            tier: 'A' },
  { ticker: 'ASM',     name: 'ASM International', tier: 'A' },
  { ticker: 'ADYEN',   name: 'Adyen',             tier: 'A' },
  { ticker: 'AD',      name: 'Ahold Delhaize',    tier: 'A' },
]

const UK_COMPANIES: EarningsCompany[] = [
  { ticker: 'AZN',     name: 'AstraZeneca',       tier: 'S' },
  { ticker: 'HSBA',    name: 'HSBC',              tier: 'S' },
  { ticker: 'SHEL',    name: 'Shell',             tier: 'S' },
  { ticker: 'ULVR',    name: 'Unilever',          tier: 'A' },
  { ticker: 'RR',      name: 'Rolls-Royce',       tier: 'A' },
  { ticker: 'GSK',     name: 'GSK',               tier: 'A' },
  { ticker: 'RIO',     name: 'Rio Tinto',         tier: 'A' },
  { ticker: 'BP',      name: 'BP',                tier: 'A' },
  { ticker: 'NG',      name: 'National Grid',     tier: 'A' },
]

const SWITZERLAND_COMPANIES: EarningsCompany[] = [
  { ticker: 'ROG',     name: 'Roche',             tier: 'S' },
  { ticker: 'NOVN',    name: 'Novartis',          tier: 'S' },
  { ticker: 'NESN',    name: 'Nestlé',            tier: 'S' },
  { ticker: 'UBSG',    name: 'UBS',               tier: 'A' },
  { ticker: 'ABBN',    name: 'ABB',               tier: 'A' },
  { ticker: 'ZURN',    name: 'Zurich Insurance',  tier: 'A' },
  { ticker: 'CFR',     name: 'Richemont',         tier: 'A' },
]

const GERMANY_COMPANIES: EarningsCompany[] = [
  { ticker: 'SIE',     name: 'Siemens',           tier: 'S' },
  { ticker: 'SAP',     name: 'SAP',               tier: 'S' },
  { ticker: 'ALV',     name: 'Allianz',           tier: 'A' },
  { ticker: 'ENR',     name: 'Siemens Energy',    tier: 'A' },
  { ticker: 'DTE',     name: 'Deutsche Telekom',  tier: 'A' },
  { ticker: 'IFX',     name: 'Infineon',          tier: 'A' },
  { ticker: 'DBK',     name: 'Deutsche Bank',     tier: 'A' },
  { ticker: 'MUV2',    name: 'Munich Re',         tier: 'A' },
  { ticker: 'RHM',     name: 'Rheinmetall',       tier: 'A' },
]

const DENMARK_COMPANIES: EarningsCompany[] = [
  { ticker: 'NOVO-B',  name: 'Novo Nordisk',      tier: 'S' },
  { ticker: 'DSV',     name: 'DSV',               tier: 'A' },
  { ticker: 'DANSKE',  name: 'Danske Bank',       tier: 'A' },
  { ticker: 'VWS',     name: 'Vestas',            tier: 'A' },
  { ticker: 'NZYM-B',  name: 'Novonesis',         tier: 'A' },
  { ticker: 'GMAB',    name: 'Genmab',            tier: 'A' },
  { ticker: 'MAERSK-B',name: 'AP Moller Maersk',  tier: 'A' },
]

const FRANCE_COMPANIES: EarningsCompany[] = [
  { ticker: 'SU',      name: 'Schneider Electric',tier: 'A' },
  { ticker: 'MC',      name: 'LVMH',              tier: 'A' },
  { ticker: 'TTE',     name: 'TotalEnergies',     tier: 'A' },
  { ticker: 'SAF',     name: 'Safran',            tier: 'A' },
  { ticker: 'AIR',     name: 'Airbus',            tier: 'A' },
  { ticker: 'SAN',     name: 'Sanofi',            tier: 'A' },
  { ticker: 'BNP',     name: 'BNP Paribas',       tier: 'A' },
  { ticker: 'CS',      name: 'AXA',               tier: 'A' },
]

const TAIWAN_COMPANIES: EarningsCompany[] = [
  { ticker: 'TSM',     name: 'TSMC',              tier: 'S' },
  { ticker: '2317.TW', name: 'Hon Hai',           tier: 'A' },
  { ticker: '2454.TW', name: 'MediaTek',          tier: 'A', noFinancials: true },
]

const SOUTHKOREA_COMPANIES: EarningsCompany[] = [
  { ticker: '005930.KS', name: 'Samsung Electronics', tier: 'S' },
  { ticker: '000660.KS', name: 'SK hynix',             tier: 'S', noFinancials: true },
  { ticker: '005380.KS', name: 'Hyundai Motor',        tier: 'A' },
  { ticker: '105560.KS', name: 'KB Financial',         tier: 'A' },
  { ticker: '000270.KS', name: 'Kia',                  tier: 'A', noFinancials: true },
  { ticker: '055550.KS', name: 'Shinhan Financial',    tier: 'A' },
  { ticker: '012450.KS', name: 'Hanwha Aerospace',     tier: 'A', noFinancials: true },
  { ticker: '034020.KS', name: 'Doosan Enerbility',    tier: 'A', noFinancials: true },
]

const CHINA_HK_COMPANIES: EarningsCompany[] = [
  { ticker: '0700.HK',   name: 'Tencent',               tier: 'S' },
  { ticker: 'BABA',      name: 'Alibaba',               tier: 'S' },
  { ticker: '1810.HK',   name: 'Xiaomi',                tier: 'A' },
  { ticker: 'PDD',       name: 'PDD',                   tier: 'A' },
  { ticker: '3690.HK',   name: 'Meituan',               tier: 'A' },
  { ticker: '1211.HK',   name: 'BYD',                   tier: 'A' },
  { ticker: '0939.HK',   name: 'China Construction Bank',tier: 'B' },
  { ticker: '2318.HK',   name: 'Ping An',               tier: 'B' },
  { ticker: '1398.HK',   name: 'ICBC',                  tier: 'B' },
  { ticker: '3988.HK',   name: 'Bank of China',         tier: 'B' },
]

const INDIA_COMPANIES: EarningsCompany[] = [
  { ticker: 'HDFCBANK.NS', name: 'HDFC Bank',              tier: 'S' },
  { ticker: 'RELIANCE.NS', name: 'Reliance Industries',    tier: 'S', noFinancials: true },
  { ticker: 'ICICIBANK.NS',name: 'ICICI Bank',             tier: 'S' },
  { ticker: 'BHARTIARTL.NS',name:'Bharti Airtel',          tier: 'A', noFinancials: true },
  { ticker: 'INFY.NS',     name: 'Infosys',               tier: 'A' },
  { ticker: 'AXISBANK.NS', name: 'Axis Bank',             tier: 'A', noFinancials: true },
  { ticker: 'LT.NS',       name: 'Larsen & Toubro',       tier: 'A' },
  { ticker: 'M&M.NS',      name: 'Mahindra & Mahindra',   tier: 'A' },
  { ticker: 'TCS.NS',      name: 'Tata Consultancy',      tier: 'A', noFinancials: true },
  { ticker: 'BAJFINANCE.NS',name:'Bajaj Finance',          tier: 'A', noFinancials: true },
]

const CANADA_COMPANIES: EarningsCompany[] = [
  { ticker: 'RY',      name: 'Royal Bank of Canada',        tier: 'A' },
  { ticker: 'TD',      name: 'TD',                          tier: 'A' },
  { ticker: 'SHOP',    name: 'Shopify',                     tier: 'A' },
  { ticker: 'AEM',     name: 'Agnico Eagle',                tier: 'A' },
  { ticker: 'ENB',     name: 'Enbridge',                    tier: 'A' },
  { ticker: 'CNQ',     name: 'Canadian Natural Resources',  tier: 'A' },
  { ticker: 'BAM',     name: 'Brookfield',                  tier: 'A' },
]

const AUSTRALIA_COMPANIES: EarningsCompany[] = [
  { ticker: 'BHP.AX',  name: 'BHP',                tier: 'A' },
  { ticker: 'CBA.AX',  name: 'Commonwealth Bank',  tier: 'A' },
  { ticker: 'NAB.AX',  name: 'NAB',                tier: 'A' },
  { ticker: 'WBC.AX',  name: 'Westpac',            tier: 'A' },
  { ticker: 'ANZ.AX',  name: 'ANZ',                tier: 'A' },
  { ticker: 'MQG.AX',  name: 'Macquarie',          tier: 'A' },
  { ticker: 'CSL.AX',  name: 'CSL',                tier: 'A' },
  { ticker: 'RIO.AX',  name: 'Rio Tinto Ltd',      tier: 'A' },
]

// -----------------------------------------------------------------------
// Countries list
// -----------------------------------------------------------------------

export const EARNINGS_COUNTRIES: EarningsCountryItem[] = [
  { code: 'usa',           name: 'United States',    nameJa: 'アメリカ',       flag: '🇺🇸', color: '#3b82f6', companies: USA_COMPANIES },
  { code: 'japan',         name: 'Japan',            nameJa: '日本',           flag: '🇯🇵', color: '#ef4444', companies: JAPAN_COMPANIES },
  { code: 'netherlands',   name: 'Netherlands',      nameJa: 'オランダ',       flag: '🇳🇱', color: '#f97316', companies: NETHERLANDS_COMPANIES },
  { code: 'uk',            name: 'United Kingdom',   nameJa: 'イギリス',       flag: '🇬🇧', color: '#8b5cf6', companies: UK_COMPANIES },
  { code: 'switzerland',   name: 'Switzerland',      nameJa: 'スイス',         flag: '🇨🇭', color: '#ec4899', companies: SWITZERLAND_COMPANIES },
  { code: 'germany',       name: 'Germany',          nameJa: 'ドイツ',         flag: '🇩🇪', color: '#f59e0b', companies: GERMANY_COMPANIES },
  { code: 'denmark',       name: 'Denmark',          nameJa: 'デンマーク',     flag: '🇩🇰', color: '#84cc16', companies: DENMARK_COMPANIES },
  { code: 'france',        name: 'France',           nameJa: 'フランス',       flag: '🇫🇷', color: '#06b6d4', companies: FRANCE_COMPANIES },
  { code: 'taiwan',        name: 'Taiwan',           nameJa: '台湾',           flag: '🇹🇼', color: '#14b8a6', companies: TAIWAN_COMPANIES },
  { code: 'southkorea',    name: 'South Korea',      nameJa: '韓国',           flag: '🇰🇷', color: '#0ea5e9', companies: SOUTHKOREA_COMPANIES },
  { code: 'china-hongkong',name: 'China / Hong Kong',nameJa: '中国・香港',     flag: '🇨🇳', color: '#dc2626', companies: CHINA_HK_COMPANIES },
  { code: 'india',         name: 'India',            nameJa: 'インド',         flag: '🇮🇳', color: '#d97706', companies: INDIA_COMPANIES },
  { code: 'canada',        name: 'Canada',           nameJa: 'カナダ',         flag: '🇨🇦', color: '#ef4444', companies: CANADA_COMPANIES },
  { code: 'australia',     name: 'Australia',        nameJa: 'オーストラリア', flag: '🇦🇺', color: '#10b981', companies: AUSTRALIA_COMPANIES },
]

// -----------------------------------------------------------------------
// Category definitions (calendar / data)
// -----------------------------------------------------------------------

export const EARNINGS_CATEGORIES_DATA: EarningsCategoryItem[] = [
  {
    code: 'calendar',
    name: 'Earnings Calendar',
    nameJa: '決算カレンダー',
    icon: <CalendarOutlined />,
    color: '#10b981',
    description: '全世界・各国企業の決算発表スケジュール',
  },
  {
    code: 'data',
    name: 'Earnings Data',
    nameJa: '決算データ',
    icon: <BarChartOutlined />,
    color: '#3b82f6',
    description: '各国企業の決算結果・EPS/売上サプライズ',
  },
]

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

export function getEarningsCategory(code: string): EarningsCategoryItem | undefined {
  return EARNINGS_CATEGORIES_DATA.find((c) => c.code === code)
}

export function getEarningsCountry(countryCode: string): EarningsCountryItem | undefined {
  return EARNINGS_COUNTRIES.find((c) => c.code === countryCode)
}

/** 全国企業をフラットに返す（全国カレンダー用） */
export function getAllCompanies(): (EarningsCompany & { countryCode: string; countryNameJa: string; flag: string })[] {
  return EARNINGS_COUNTRIES.flatMap((country) =>
    country.companies.map((c) => ({
      ...c,
      countryCode: country.code,
      countryNameJa: country.nameJa,
      flag: country.flag,
    }))
  )
}

/** ティッカーリストを国コードから返す（バックエンドクエリ用） */
export function getTickersByCountry(countryCode: string): string[] {
  const country = getEarningsCountry(countryCode)
  return country ? country.companies.map((c) => c.ticker) : []
}
