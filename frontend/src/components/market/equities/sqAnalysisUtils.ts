/**
 * SQ / MSQ 分析テーブル — 色付け・強調表示・バッジ・サマリー生成ユーティリティ
 *
 * 設計方針:
 *   優先順位: 10年データ > 中央値 > 上昇確率 > 平均 > N
 *   強調は単一数値ではなく、平均・中央値・上昇確率・N の整合性で判定
 *   ダークテーマ前提
 */

// ====================================================================
// 1. 型定義
// ====================================================================

export type BiasLabel = '強気' | 'やや強気' | '中立' | 'やや弱気' | '弱気' | '参考強気' | '参考弱気'

export type ReturnStrength = 'noise' | 'weak' | 'medium' | 'strong' | 'veryStrong'

export type WinRateStrength =
  | 'veryStrongBull'
  | 'strongBull'
  | 'weakBull'
  | 'neutral'
  | 'weakBear'
  | 'strongBear'
  | 'veryStrongBear'

export type NConfidence = 'high' | 'normal' | 'low' | 'veryLow' | 'minimal'

/** 優先度A行 (背景ハイライト・バッジ許可) */
export const PRIORITY_A_KEYS = new Set([
  '前2日間合計',
  '前日→SQ日',
  'SQ当日(始値→終値)',
  'SQ→翌営業日',
])

// ====================================================================
// 2. 分類関数
// ====================================================================

/** 平均・中央値の強弱判定 */
export function strengthByReturn(x: number | null | undefined): ReturnStrength {
  if (x == null) return 'noise'
  const a = Math.abs(x)
  if (a < 0.10) return 'noise'
  if (a < 0.20) return 'weak'
  if (a < 0.30) return 'medium'
  if (a < 0.50) return 'strong'
  return 'veryStrong'
}

/** 上昇確率の強弱判定 */
export function strengthByWinRate(w: number | null | undefined): WinRateStrength {
  if (w == null) return 'neutral'
  if (w >= 65) return 'veryStrongBull'
  if (w >= 60) return 'strongBull'
  if (w > 55) return 'weakBull'
  if (w >= 45) return 'neutral'
  if (w > 40) return 'weakBear'
  if (w >= 35) return 'strongBear'
  return 'veryStrongBear'
}

/** N の信頼度判定 */
export function confidenceByN(n: number): NConfidence {
  if (n >= 100) return 'high'
  if (n >= 50) return 'normal'
  if (n >= 30) return 'low'
  if (n >= 15) return 'veryLow'
  return 'minimal'
}

/**
 * 全体表・10年表の行ラベル判定（数値色より厳しい基準）
 *
 * 強気:     avg >= 0.20, median >= 0.15, winRate >= 60, n >= 30, 同符号
 * やや強気: avg >= 0.10, median >= 0.10, winRate >= 57.5, n >= 30, 同符号
 * 弱気:     avg <= -0.20, median <= -0.15, winRate <= 40, n >= 30, 同符号
 * やや弱気: avg <= -0.10, median <= -0.10, winRate <= 42.5, n >= 30, 同符号
 * それ以外: ラベルなし (中立)
 */
export function classifyBias(
  avg: number | null | undefined,
  median: number | null | undefined,
  winRate: number | null | undefined,
  n: number,
): BiasLabel {
  if (avg == null || median == null || winRate == null || n < 30) return '中立'

  const samePositive = avg > 0 && median > 0
  const sameNegative = avg < 0 && median < 0

  // 逆方向 or 数値が小さすぎる → ラベルなし
  if (!samePositive && !sameNegative) return '中立'
  if (Math.abs(avg) < 0.10 || Math.abs(median) < 0.10) return '中立'
  if (winRate > 42.5 && winRate < 57.5) return '中立'

  // 強気判定
  if (samePositive && avg >= 0.20 && median >= 0.15 && winRate >= 60) return '強気'
  if (samePositive && avg >= 0.10 && median >= 0.10 && winRate >= 57.5) return 'やや強気'

  // 弱気判定
  if (sameNegative && avg <= -0.20 && median <= -0.15 && winRate <= 40) return '弱気'
  if (sameNegative && avg <= -0.10 && median <= -0.10 && winRate <= 42.5) return 'やや弱気'

  return '中立'
}

/**
 * 月別表のラベル判定
 *
 * 原則ラベルなし。例外的に以下をすべて満たす場合のみ 参考強気 / 参考弱気:
 * - n >= 10
 * - avg と median が同方向
 * - abs(avg) >= 0.20
 * - abs(median) >= 0.20
 * - winRate >= 65 or winRate <= 35
 */
export function classifyMonthlyBias(
  avg: number | null | undefined,
  median: number | null | undefined,
  winRate: number | null | undefined,
  n: number,
): BiasLabel {
  if (avg == null || median == null || winRate == null || n < 10) return '中立'

  const samePositive = avg > 0 && median > 0
  const sameNegative = avg < 0 && median < 0

  if (samePositive && avg >= 0.20 && median >= 0.20 && winRate >= 65) return '参考強気'
  if (sameNegative && avg <= -0.20 && median <= -0.20 && winRate <= 35) return '参考弱気'

  return '中立'
}

// ====================================================================
// 3. 色パレット (ダークテーマ)
// ====================================================================

const COLORS = {
  // 緑系 (ポジティブ)
  positiveVeryStrong: '#10b981',  // emerald-500
  positiveStrong:     '#34d399',  // emerald-400
  positiveMedium:     '#6ee7b7',  // emerald-300
  positiveWeak:       '#6ee7b780', // emerald-300 50% alpha
  // 赤系 (ネガティブ)
  negativeVeryStrong: '#ef4444',  // red-500
  negativeStrong:     '#f87171',  // red-400
  negativeMedium:     '#fca5a5',  // red-300
  negativeWeak:       '#fca5a580', // red-300 50% alpha
  // 中立
  neutral:            '#94a3b8',  // slate-400
  textPrimary:        '#f1f5f9',  // slate-100
  textSecondary:      '#94a3b8',  // slate-400
  // N の信頼度
  nHigh:              '#f1f5f9',
  nNormal:            '#cbd5e1',
  nLow:               '#94a3b8',
  nVeryLow:           '#fbbf24',  // amber-400
  nMinimal:           '#64748b',  // slate-500
  // 行背景
  rowBullStrong:      'rgba(16, 185, 129, 0.10)',
  rowBullWeak:        'rgba(16, 185, 129, 0.05)',
  rowBearStrong:      'rgba(239, 68, 68, 0.10)',
  rowBearWeak:        'rgba(239, 68, 68, 0.05)',
  // バッジ
  badgeBull:          '#065f46',  // emerald-800
  badgeBullText:      '#6ee7b7',  // emerald-300
  badgeBear:          '#7f1d1d',  // red-900
  badgeBearText:      '#fca5a5',  // red-300
  badgeNeutral:       '#334155',  // slate-700
  badgeNeutralText:   '#94a3b8',  // slate-400
  badgeRef:           '#422006',  // amber-950
  badgeRefText:       '#fbbf24',  // amber-400
} as const

// ====================================================================
// 4. 色取得関数
// ====================================================================

/** 平均・中央値 → セルテキスト色 */
export function returnColor(val: number | null | undefined, monthly = false): string {
  if (val == null) return COLORS.neutral
  const strength = strengthByReturn(val)
  if (strength === 'noise') return COLORS.neutral

  const positive = val > 0
  // 月別は1段階薄くする
  if (monthly) {
    if (positive) {
      return strength === 'veryStrong' || strength === 'strong'
        ? COLORS.positiveMedium
        : COLORS.positiveWeak
    }
    return strength === 'veryStrong' || strength === 'strong'
      ? COLORS.negativeMedium
      : COLORS.negativeWeak
  }

  if (positive) {
    switch (strength) {
      case 'veryStrong': return COLORS.positiveVeryStrong
      case 'strong':     return COLORS.positiveStrong
      case 'medium':     return COLORS.positiveMedium
      case 'weak':       return COLORS.positiveWeak
    }
  } else {
    switch (strength) {
      case 'veryStrong': return COLORS.negativeVeryStrong
      case 'strong':     return COLORS.negativeStrong
      case 'medium':     return COLORS.negativeMedium
      case 'weak':       return COLORS.negativeWeak
    }
  }
  return COLORS.neutral
}

/** 上昇確率 → セルテキスト色 */
export function winRateColor(val: number | null | undefined, monthly = false): string {
  if (val == null) return COLORS.neutral
  const s = strengthByWinRate(val)
  if (s === 'neutral') return COLORS.neutral

  if (monthly) {
    if (s.includes('Bull')) return COLORS.positiveWeak
    return COLORS.negativeWeak
  }

  switch (s) {
    case 'veryStrongBull': return COLORS.positiveVeryStrong
    case 'strongBull':     return COLORS.positiveMedium
    case 'weakBull':       return COLORS.positiveWeak
    case 'weakBear':       return COLORS.negativeWeak
    case 'strongBear':     return COLORS.negativeMedium
    case 'veryStrongBear': return COLORS.negativeVeryStrong
  }
  return COLORS.neutral
}

/** N → テキスト色 */
export function nColor(n: number): string {
  switch (confidenceByN(n)) {
    case 'high':    return COLORS.nHigh
    case 'normal':  return COLORS.nNormal
    case 'low':     return COLORS.nLow
    case 'veryLow': return COLORS.nVeryLow
    case 'minimal': return COLORS.nMinimal
  }
}

/** セルの太字判定 (強気/弱気 + 優先度A行) */
export function shouldBold(
  val: number | null | undefined,
  bias: BiasLabel,
  isPriorityA: boolean,
  type: 'return' | 'winRate',
): boolean {
  if (!isPriorityA) return false
  if (bias !== '強気' && bias !== '弱気') return false
  if (val == null) return false
  if (type === 'return') {
    const s = strengthByReturn(val)
    return s === 'strong' || s === 'veryStrong'
  }
  const s = strengthByWinRate(val)
  return s === 'veryStrongBull' || s === 'veryStrongBear'
}

/** ラベルが表示対象か (中立はラベルなし) */
export function hasVisibleLabel(bias: BiasLabel): boolean {
  return bias !== '中立'
}

// ====================================================================
// 5. 行ハイライト
// ====================================================================

export interface RowStyle {
  background: string | undefined
  badge: BiasLabel
  showBadge: boolean
  showDot: boolean
}

export function getRowStyle(
  avg: number | null | undefined,
  median: number | null | undefined,
  winRate: number | null | undefined,
  n: number,
  rowKey: string,
  monthly = false,
): RowStyle {
  const bias = monthly
    ? classifyMonthlyBias(avg, median, winRate, n)
    : classifyBias(avg, median, winRate, n)
  const isPriorityA = PRIORITY_A_KEYS.has(rowKey)

  let background: string | undefined
  let showBadge = false
  let showDot = false

  if (monthly) {
    // 月別: 行背景なし。参考強気/参考弱気のみバッジ表示
    if (bias === '参考強気' || bias === '参考弱気') {
      showBadge = true
    }
  } else if (isPriorityA && bias !== '中立') {
    // 全体表: 優先度A行のみ背景ハイライト・バッジ・ドット
    if (bias === '強気') {
      const isVeryStrong = (avg != null && Math.abs(avg) >= 0.30) || (median != null && Math.abs(median) >= 0.30)
      background = isVeryStrong ? COLORS.rowBullStrong : COLORS.rowBullWeak
      showBadge = true
      showDot = true
    } else if (bias === 'やや強気') {
      background = COLORS.rowBullWeak
      showBadge = true
    } else if (bias === '弱気') {
      const isVeryStrong = (avg != null && Math.abs(avg) >= 0.30) || (median != null && Math.abs(median) >= 0.30)
      background = isVeryStrong ? COLORS.rowBearStrong : COLORS.rowBearWeak
      showBadge = true
      showDot = true
    } else if (bias === 'やや弱気') {
      background = COLORS.rowBearWeak
      showBadge = true
    }
  }

  return { background, badge: bias, showBadge, showDot }
}

// ====================================================================
// 6. バッジ表示
// ====================================================================

export interface BadgeStyle {
  backgroundColor: string
  color: string
  label: string
}

export function getBadgeStyle(bias: BiasLabel): BadgeStyle {
  switch (bias) {
    case '強気':
      return { backgroundColor: COLORS.badgeBull, color: COLORS.badgeBullText, label: '強気' }
    case 'やや強気':
      return { backgroundColor: COLORS.badgeBull, color: COLORS.badgeBullText, label: 'やや強気' }
    case '弱気':
      return { backgroundColor: COLORS.badgeBear, color: COLORS.badgeBearText, label: '弱気' }
    case 'やや弱気':
      return { backgroundColor: COLORS.badgeBear, color: COLORS.badgeBearText, label: 'やや弱気' }
    case '参考強気':
      return { backgroundColor: COLORS.badgeRef, color: COLORS.badgeRefText, label: '参考強気' }
    case '参考弱気':
      return { backgroundColor: COLORS.badgeRef, color: COLORS.badgeRefText, label: '参考弱気' }
    default:
      return { backgroundColor: COLORS.badgeNeutral, color: COLORS.badgeNeutralText, label: '中立' }
  }
}

// ====================================================================
// 7. N のツールチップ
// ====================================================================

export function nTooltip(n: number): string | null {
  const c = confidenceByN(n)
  if (c === 'veryLow') return 'サンプル数が少ないため過信注意'
  if (c === 'minimal') return 'サンプル数が非常に少なく参考程度'
  return null
}

// ====================================================================
// 8. サマリー文自動生成
// ====================================================================

interface SummaryRowData {
  key: string
  mean: number | null
  median: number | null
  win_rate: number | null
  count: number
}

/**
 * テーブル上部に表示する短い解説文を生成。
 * 10年データを優先、優先度A行を中心に傾向を要約。
 */
export function generateSummary(
  rows: SummaryRowData[],
  periodLabel: string,
): string {
  // 優先度A行から最も傾向の強い行を選ぶ
  const priorityRows = rows.filter(r => PRIORITY_A_KEYS.has(r.key))
  if (priorityRows.length === 0) return ''

  // 各行のバイアスを計算、強い順に並べる
  const biasOrder: Record<BiasLabel, number> = {
    '強気': 5, '弱気': 5, 'やや強気': 3, 'やや弱気': 3, '参考強気': 1, '参考弱気': 1, '中立': 0,
  }
  const scored = priorityRows
    .map(r => ({
      ...r,
      bias: classifyBias(r.mean, r.median, r.win_rate, r.count),
    }))
    .sort((a, b) => biasOrder[b.bias] - biasOrder[a.bias])

  const top = scored[0]
  if (!top || top.bias === '中立') {
    return `${periodLabel}では、各期間とも平均・中央値・上昇確率の整合性が弱く、明確な優位性は確認しにくい状況です。`
  }

  const dirLabel = top.bias === '強気' || top.bias === 'やや強気' ? '上昇' : '下落'
  const strength = top.bias === '強気' || top.bias === '弱気' ? '' : 'やや'
  const meanStr = top.mean != null ? `平均 ${top.mean > 0 ? '+' : ''}${top.mean.toFixed(2)}%` : ''
  const medianStr = top.median != null ? `中央値 ${top.median > 0 ? '+' : ''}${top.median.toFixed(2)}%` : ''
  const wrStr = top.win_rate != null ? `上昇確率 ${top.win_rate.toFixed(1)}%` : ''
  const stats = [meanStr, medianStr, wrStr].filter(Boolean).join('、')

  return `${periodLabel}では、「${top.key}」は${stats}と、${strength}${dirLabel}しやすい傾向が見られます。`
}

/**
 * 月別テーブル向け注記文を生成。
 * 強い月があればピックアップ。
 */
export function generateMonthlySummary(
  rows: SummaryRowData[],
  fieldLabel: string,
): string {
  const strong = rows.filter(r => {
    const bias = classifyMonthlyBias(r.mean, r.median, r.win_rate, r.count)
    return bias === '参考強気' || bias === '参考弱気'
  })

  if (strong.length === 0) {
    return `月別（${fieldLabel}）は全体的に明確な偏りが見られません。月別はサンプル数が少ないため補助的に参照してください。`
  }

  const parts = strong.map(r => {
    const dir = r.mean != null && r.mean > 0 ? '上昇' : '下落'
    return `${r.key}（${dir}寄り）`
  })

  return `月別（${fieldLabel}）では${parts.join('、')}に偏りが見られますが、サンプル数が限られるため補助的な傾向として扱ってください。`
}

// ====================================================================
// 9. エクスポート用定数
// ====================================================================

export { COLORS as SQ_COLORS }
