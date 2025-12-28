/**
 * 月別データテーブルコンポーネント
 *
 * 年×月のマトリックス形式でデータを表示
 */
import React from 'react'
import { MONTH_NAMES, getCellColor, getValueColor, MOM_THRESHOLDS, DARK_THEME, TEXT_COLORS } from './chartConstants'
import { TableLegend, MOM_LEGEND_DEFAULT, MOM_LEGEND_VEHICLE } from './ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface MonthlyTableData<T = number> {
  years: number[]
  monthlyData: Record<number, Record<number, T | null>>
}

interface MonthlyTableProps<T = number> {
  /** テーブルデータ（年×月のマトリックス） */
  data: MonthlyTableData<T>
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
  /** 閾値タイプ（'default' | 'vehicle'） */
  thresholdType?: 'default' | 'vehicle'
  /** ヘルパーテキストを表示するか（デフォルト: true） */
  showHelperText?: boolean
  /** カスタムヘルパーテキスト */
  helperText?: string
}

// =============================================================================
// MonthlyTable コンポーネント
// =============================================================================

/** デフォルトのヘルパーテキスト */
const DEFAULT_HELPER_TEXT = '※ 直近10年間の前月比データ（単位: %）'

export function MonthlyTable<T extends number = number>({
  data,
  formatValue,
  getCellBgColor,
  getTextColor,
  showLegend = true,
  legendItems,
  header,
  decimals = 2,
  thresholdType = 'default',
  showHelperText = true,
  helperText = DEFAULT_HELPER_TEXT,
}: MonthlyTableProps<T>) {
  const thresholds = thresholdType === 'vehicle' ? MOM_THRESHOLDS.vehicle : MOM_THRESHOLDS.default
  const defaultLegend = thresholdType === 'vehicle' ? MOM_LEGEND_VEHICLE : MOM_LEGEND_DEFAULT

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
            {MONTH_NAMES.map((month, idx) => (
              <th
                key={idx}
                style={{
                  padding: '8px 4px',
                  borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                  fontWeight: 'bold',
                  minWidth: 50,
                }}
              >
                {month}
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
              {Array.from({ length: 12 }, (_, month) => {
                const value = data.monthlyData[year]?.[month] ?? null
                const displayValue = formatFn(value)
                const bgColor = bgColorFn(value)
                const textColor = textColorFn(value)

                return (
                  <td
                    key={month}
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

      {showLegend && <TableLegend items={legendItems || defaultLegend} />}
    </div>
  )
}

// =============================================================================
// MonthlyTableWithDataTypes - データタイプ切り替え付きテーブル
// =============================================================================

interface DataTypeConfig<T extends string> {
  type: T
  label: string
}

interface MultiValueMonthlyData<T extends string> {
  years: number[]
  monthlyData: Record<number, Record<number, Record<T, number | null> | null>>
}

interface MonthlyTableWithDataTypesProps<T extends string> {
  /** テーブルデータ（年×月のマトリックス、各セルに複数のデータタイプ） */
  data: MultiValueMonthlyData<T>
  /** データタイプの設定 */
  dataTypes: DataTypeConfig<T>[]
  /** 選択中のデータタイプ */
  selectedType: T
  /** データタイプ変更時のコールバック */
  onTypeChange: (type: T) => void
  /** 凡例を表示するかどうか */
  showLegend?: boolean
  /** 閾値タイプ */
  thresholdType?: 'default' | 'vehicle'
  /** 小数点以下の桁数 */
  decimals?: number
  /** ヘルパーテキストを表示するか（デフォルト: true） */
  showHelperText?: boolean
  /** カスタムヘルパーテキスト */
  helperText?: string
}

export function MonthlyTableWithDataTypes<T extends string>({
  data,
  dataTypes,
  selectedType,
  onTypeChange,
  showLegend = true,
  thresholdType = 'default',
  decimals = 2,
  showHelperText = true,
  helperText = DEFAULT_HELPER_TEXT,
}: MonthlyTableWithDataTypesProps<T>) {
  const thresholds = thresholdType === 'vehicle' ? MOM_THRESHOLDS.vehicle : MOM_THRESHOLDS.default
  const defaultLegend = thresholdType === 'vehicle' ? MOM_LEGEND_VEHICLE : MOM_LEGEND_DEFAULT

  // データタイプボタン用のスタイル設定（ダークテーマ）
  const buttonConfigs: Record<string, { color: string; bgColor: string }> = {
    total: { color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.15)' },
    ex_auto: { color: '#a855f7', bgColor: 'rgba(168, 85, 247, 0.15)' },
    control_group: { color: '#06b6d4', bgColor: 'rgba(6, 182, 212, 0.15)' },
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
      {showHelperText && (
        <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 12 }}>
          {helperText}
        </div>
      )}
      {/* データタイプ切り替えボタン */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        {dataTypes.map(({ type, label }) => {
          const isActive = type === selectedType
          const config = buttonConfigs[type] || { color: '#3b82f6', bgColor: 'rgba(59, 130, 246, 0.15)' }

          return (
            <button
              key={type}
              onClick={() => onTypeChange(type)}
              style={{
                padding: '4px 10px',
                border: isActive ? `2px solid ${config.color}` : `1px solid ${DARK_THEME.border}`,
                borderRadius: 4,
                background: isActive ? config.bgColor : DARK_THEME.bgSecondary,
                cursor: 'pointer',
                fontWeight: isActive ? 'bold' : 'normal',
                fontSize: 12,
                color: isActive ? config.color : DARK_THEME.textSecondary,
              }}
            >
              {label}
            </button>
          )
        })}
      </div>

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
            {MONTH_NAMES.map((month, idx) => (
              <th
                key={idx}
                style={{
                  padding: '8px 4px',
                  borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                  fontWeight: 'bold',
                  minWidth: 50,
                }}
              >
                {month}
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
              {Array.from({ length: 12 }, (_, month) => {
                const cellData = data.monthlyData[year]?.[month]
                const value = cellData ? cellData[selectedType] : null
                const bgColor = getCellColor(value, thresholds)
                const textColor = getValueColor(value)

                return (
                  <td
                    key={month}
                    style={{
                      padding: '6px 4px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      backgroundColor: bgColor,
                    }}
                  >
                    {value !== null && value !== undefined ? (
                      <span style={{ color: textColor }}>
                        {value >= 0 ? '+' : ''}
                        {value.toFixed(decimals)}
                      </span>
                    ) : (
                      <span style={{ color: TEXT_COLORS.quaternary }}>-</span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {showLegend && <TableLegend items={defaultLegend} />}
    </div>
  )
}

export default MonthlyTable
