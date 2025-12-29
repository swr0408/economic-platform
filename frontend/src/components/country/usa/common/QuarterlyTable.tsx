/**
 * 四半期データテーブルコンポーネント
 *
 * 年×四半期のマトリックス形式でデータを表示
 */
import React from 'react'
import { QUARTER_NAMES, getCellColor, getValueColor, MOM_THRESHOLDS, DARK_THEME, TEXT_COLORS } from './chartConstants'
import { TableLegend } from './ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface QuarterlyTableData<T = number> {
  years: number[]
  quarterlyData: Record<number, Record<number, T | null>>
}

interface QuarterlyTableProps<T = number> {
  /** テーブルデータ（年×四半期のマトリックス） */
  data: QuarterlyTableData<T>
  /** 値を文字列にフォーマットする関数 */
  formatValue?: (value: T | null) => string
  /** 値からセル背景色を決定する関数 */
  getCellBgColor?: (value: T | null) => string
  /** 値からテキストカラーを決定する関数 */
  getTextColor?: (value: T | null) => string
  /** 凡例を表示するかどうか */
  showLegend?: boolean
  /** カスタム凡例アイテム */
  legendItems?: { color: string; label: string }[]
  /** テーブル上部に表示するカスタムコンテンツ */
  header?: React.ReactNode
  /** 小数点以下の桁数 */
  decimals?: number
  /** ヘルパーテキストを表示するか（デフォルト: true） */
  showHelperText?: boolean
  /** カスタムヘルパーテキスト */
  helperText?: string
}

// =============================================================================
// QuarterlyTable コンポーネント
// =============================================================================

/** デフォルトのヘルパーテキスト */
const DEFAULT_HELPER_TEXT = '※ 直近10年間の前期比データ（単位: %）'

export function QuarterlyTable<T extends number = number>({
  data,
  formatValue,
  getCellBgColor,
  getTextColor,
  showLegend = true,
  legendItems,
  header,
  decimals = 2,
  showHelperText = true,
  helperText = DEFAULT_HELPER_TEXT,
}: QuarterlyTableProps<T>) {
  const thresholds = MOM_THRESHOLDS.default

  // デフォルトのフォーマット関数
  const defaultFormatValue = (value: T | null): string => {
    if (value === null || value === undefined) return '-'
    const numValue = value as number
    return `${numValue >= 0 ? '+' : ''}${numValue.toFixed(decimals)}`
  }

  // デフォルトの背景色関数
  const defaultGetCellBgColor = (value: T | null): string => {
    return getCellColor(value as number | null, thresholds)
  }

  // デフォルトのテキストカラー関数
  const defaultGetTextColor = (value: T | null): string => {
    return getValueColor(value as number | null)
  }

  const formatFn = formatValue || defaultFormatValue
  const bgColorFn = getCellBgColor || defaultGetCellBgColor
  const textColorFn = getTextColor || defaultGetTextColor

  if (data.years.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0', color: TEXT_COLORS.tertiary }}>
        データがありません
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      {showHelperText && (
        <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 12 }}>
          {helperText}
        </div>
      )}
      {header}
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 12,
          textAlign: 'center',
          color: DARK_THEME.textPrimary,
        }}
      >
        <thead>
          <tr style={{ backgroundColor: DARK_THEME.bgTertiary }}>
            <th
              style={{
                padding: '8px 4px',
                borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                fontWeight: 'bold',
              }}
            >
              年
            </th>
            {QUARTER_NAMES.map((quarter, idx) => (
              <th
                key={idx}
                style={{
                  padding: '8px 4px',
                  borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                  fontWeight: 'bold',
                  minWidth: 80,
                }}
              >
                {quarter}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.years.map((year) => (
            <tr key={year}>
              <td
                style={{
                  padding: '6px 4px',
                  borderBottom: `1px solid ${DARK_THEME.border}`,
                  fontWeight: 'bold',
                  backgroundColor: DARK_THEME.bgTertiary,
                }}
              >
                {year}
              </td>
              {Array.from({ length: 4 }, (_, quarter) => {
                const value = data.quarterlyData[year]?.[quarter] ?? null
                const displayValue = formatFn(value)
                const bgColor = bgColorFn(value)
                const textColor = textColorFn(value)

                return (
                  <td
                    key={quarter}
                    style={{
                      padding: '6px 4px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      backgroundColor: bgColor,
                    }}
                  >
                    <span style={{ color: value === null ? TEXT_COLORS.quaternary : textColor }}>
                      {displayValue}
                    </span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {showLegend && legendItems && <TableLegend items={legendItems} />}
    </div>
  )
}

// =============================================================================
// QuarterlyTableWithDataTypes - データタイプ切り替え付きテーブル
// =============================================================================

interface DataTypeConfig<T extends string> {
  type: T
  label: string
  color?: string
  bgColor?: string
}

interface MultiValueQuarterlyData<T extends string> {
  years: number[]
  quarterlyData: Record<number, Record<number, Record<T, number | null> | null>>
}

interface QuarterlyTableWithDataTypesProps<T extends string> {
  /** テーブルデータ（年×四半期のマトリックス、各セルに複数のデータタイプ） */
  data: MultiValueQuarterlyData<T>
  /** データタイプの設定 */
  dataTypes: DataTypeConfig<T>[]
  /** 選択中のデータタイプ */
  selectedType: T
  /** データタイプ変更時のコールバック */
  onTypeChange: (type: T) => void
  /** 凡例を表示するかどうか */
  showLegend?: boolean
  /** 小数点以下の桁数 */
  decimals?: number
  /** ヘルパーテキストを表示するか（デフォルト: true） */
  showHelperText?: boolean
  /** カスタムヘルパーテキスト */
  helperText?: string
  /** カスタム値フォーマット関数 */
  formatValue?: (value: number | null) => string
  /** カスタムセル背景色関数 */
  getCellBgColor?: (value: number | null) => string
  /** カスタム凡例アイテム */
  legendItems?: { color: string; label: string }[]
}

export function QuarterlyTableWithDataTypes<T extends string>({
  data,
  dataTypes,
  selectedType,
  onTypeChange,
  showLegend = true,
  decimals = 1,
  showHelperText = true,
  helperText = DEFAULT_HELPER_TEXT,
  formatValue,
  getCellBgColor,
  legendItems,
}: QuarterlyTableWithDataTypesProps<T>) {
  // カスタムまたはデフォルトの関数
  const formatFn = formatValue || ((value: number | null) => {
    if (value === null || value === undefined) return '-'
    return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}`
  })
  const bgColorFn = getCellBgColor || ((value: number | null) => getCellColor(value, MOM_THRESHOLDS.default))

  // データタイプ設定からスタイルを取得
  const getTabButtonStyle = (config: DataTypeConfig<T>, isActive: boolean) => {
    const color = config.color || '#3b82f6'
    const bgColor = config.bgColor || (isActive ? 'rgba(59, 130, 246, 0.15)' : '#fff')

    return {
      padding: '6px 16px',
      border: isActive ? `2px solid ${color}` : `1px solid ${DARK_THEME.border}`,
      borderRadius: 4,
      background: isActive ? bgColor : DARK_THEME.bgSecondary,
      cursor: 'pointer',
      fontWeight: isActive ? 'bold' as const : 'normal' as const,
      color: isActive ? color : DARK_THEME.textSecondary,
      fontSize: 13,
    }
  }

  if (data.years.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0', color: TEXT_COLORS.tertiary }}>
        データがありません
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      {/* タブ切り替えボタン */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {dataTypes.map((config) => (
          <button
            key={config.type}
            onClick={() => onTypeChange(config.type)}
            style={getTabButtonStyle(config, selectedType === config.type)}
          >
            {config.label}
          </button>
        ))}
      </div>

      {showHelperText && (
        <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 12 }}>
          {helperText}
        </div>
      )}

      {/* テーブル */}
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 12,
          textAlign: 'center',
          color: DARK_THEME.textPrimary,
        }}
      >
        <thead>
          <tr style={{ backgroundColor: DARK_THEME.bgTertiary }}>
            <th
              style={{
                padding: '8px 4px',
                borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                fontWeight: 'bold',
              }}
            >
              年
            </th>
            {QUARTER_NAMES.map((quarter, idx) => (
              <th
                key={idx}
                style={{
                  padding: '8px 4px',
                  borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                  fontWeight: 'bold',
                  minWidth: 80,
                }}
              >
                {quarter}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.years.map((year) => (
            <tr key={year}>
              <td
                style={{
                  padding: '6px 4px',
                  borderBottom: `1px solid ${DARK_THEME.border}`,
                  fontWeight: 'bold',
                  backgroundColor: DARK_THEME.bgTertiary,
                }}
              >
                {year}
              </td>
              {Array.from({ length: 4 }, (_, quarter) => {
                const cellData = data.quarterlyData[year]?.[quarter]
                const value = cellData ? cellData[selectedType] : null
                const displayValue = formatFn(value)
                const bgColor = bgColorFn(value)
                const textColor = getValueColor(value)

                return (
                  <td
                    key={quarter}
                    style={{
                      padding: '6px 4px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      backgroundColor: bgColor,
                    }}
                  >
                    <span style={{ color: value === null ? TEXT_COLORS.quaternary : textColor }}>
                      {displayValue}
                    </span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {showLegend && legendItems && <TableLegend items={legendItems} />}
    </div>
  )
}

export default QuarterlyTable
