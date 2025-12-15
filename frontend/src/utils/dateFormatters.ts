// 共通の日付パース関数
export const parseDate = (value: string): Date | null => {
  const normalized = value.length === 7 ? `${value}-01` : value
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

// 共通の日付フォーマット関数
export const formatMonthLabel = (value: string) => {
  const parsed = parseDate(value)
  if (!parsed) return value
  return `${parsed.getFullYear()}/${String(parsed.getMonth() + 1).padStart(2, '0')}`
}

export const formatQuarterLabel = (value: string) => {
  const parsed = parseDate(value)
  if (!parsed) return value
  const quarter = Math.floor(parsed.getMonth() / 3) + 1
  return `${parsed.getFullYear()}/Q${quarter}`
}

export const formatDayLabel = (value: string) => {
  const parsed = parseDate(value)
  if (!parsed) return value
  return `${parsed.getFullYear()}/${String(parsed.getMonth() + 1).padStart(2, '0')}/${String(parsed.getDate()).padStart(2, '0')}`
}
