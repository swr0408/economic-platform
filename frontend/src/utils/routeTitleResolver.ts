/**
 * パス → 表示用タイトルの解決
 *
 * document.title はページ全体で "EconAlpha" 固定の場合があるため、
 * パス情報から自動的にユーザー向けの日本語タイトルを生成する。
 * 最近見たページ機能で使用。
 */

// 国コード → 日本語名
const COUNTRY_NAMES: Record<string, string> = {
  usa: 'アメリカ',
  japan: '日本',
  eurozone: 'ユーロ圏',
  uk: 'イギリス',
  china: '中国',
  canada: 'カナダ',
  australia: 'オーストラリア',
  newzealand: 'ニュージーランド',
  switzerland: 'スイス',
  global: 'グローバル',
}

// カテゴリコード → 日本語名 (国別のサブカテゴリ)
const CATEGORY_NAMES: Record<string, string> = {
  policy: '金融政策',
  monetary_policy: '金融政策',
  economy: '景気',
  inflation: '物価',
  price: '物価',
  employment: '雇用',
  consumer: '消費',
  consumer_sentiment: '消費者心理',
  consumption: '消費',
  housing: '住宅',
  fiscal: '財政',
  trade: '貿易',
  derivatives: 'デリバティブ',
  economy_watcher: '景気ウォッチャー',
  calendar: 'カレンダー',
}

// マーケットカテゴリ
const MARKET_CATEGORIES: Record<string, string> = {
  equities: '株式',
  fx: '為替',
  rates: '金利',
  commodities: 'コモディティ',
  crypto: '仮想通貨',
  derivatives: 'デリバティブ',
  positioning: 'ポジション',
  sentiment: 'センチメント',
}

// 決算カテゴリ
const EARNINGS_CATEGORIES: Record<string, string> = {
  usa: 'アメリカ',
  japan: '日本',
  calendar: 'カレンダー',
}

// トップレベルのセクション名
const SECTION_NAMES: Record<string, string> = {
  country: 'マクロデータ',
  markets: 'マーケットデータ',
  seasonality: 'シーズナリティ',
  earnings: '決算',
  compare: 'データ比較',
  handbook: 'データハンドブック',
  inbox: 'ヘッドライン受信箱',
  saved: 'ヘッドライン保存',
}

/**
 * パスから人間可読のタイトルを生成する。
 * マッピングにないものは最後のセグメントをそのまま返す。
 */
export function resolveRouteTitle(pathname: string): string {
  const path = pathname.replace(/\/+$/, '') // 末尾スラッシュ除去
  if (!path || path === '/') return ''

  const segments = path.split('/').filter(Boolean)
  if (segments.length === 0) return ''

  const head = segments[0]

  // /country/:countryCode/:categoryCode
  if (head === 'country') {
    const country = segments[1]
    const category = segments[2]
    const countryLabel = country ? COUNTRY_NAMES[country] ?? country : ''
    const categoryLabel = category ? CATEGORY_NAMES[category] ?? category : ''
    if (countryLabel && categoryLabel) return `${countryLabel} - ${categoryLabel}`
    if (countryLabel) return `${countryLabel}`
    return 'マクロデータ'
  }

  // /markets/:categoryCode/:subCategoryCode
  if (head === 'markets') {
    const category = segments[1]
    const sub = segments[2]
    const categoryLabel = category ? MARKET_CATEGORIES[category] ?? category : ''
    if (categoryLabel && sub) return `マーケット - ${categoryLabel} / ${sub}`
    if (categoryLabel) return `マーケット - ${categoryLabel}`
    return 'マーケットデータ'
  }

  // /seasonality/:symbol
  if (head === 'seasonality') {
    const symbol = segments[1]
    if (symbol) return `シーズナリティ - ${decodeURIComponent(symbol)}`
    return 'シーズナリティ'
  }

  // /earnings/:categoryCode/:countryCode
  if (head === 'earnings') {
    const category = segments[1]
    const country = segments[2]
    const categoryLabel = category ? EARNINGS_CATEGORIES[category] ?? category : ''
    const countryLabel = country ? COUNTRY_NAMES[country] ?? country : ''
    if (categoryLabel && countryLabel) return `決算 - ${categoryLabel} / ${countryLabel}`
    if (categoryLabel) return `決算 - ${categoryLabel}`
    return '決算'
  }

  // 単純なトップレベル
  if (SECTION_NAMES[head]) {
    if (segments.length === 1) return SECTION_NAMES[head]
    return `${SECTION_NAMES[head]} - ${segments.slice(1).join(' / ')}`
  }

  // フォールバック
  return segments.join(' / ')
}
