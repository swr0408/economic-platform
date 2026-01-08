/**
 * 2系列月別データテーブルコンポーネント
 *
 * 年×月のマトリックス形式で2系列のデータを並べて表示
 * 住宅着工件数/建設許可件数など、2つの関連指標の前月比を比較表示するために使用
 */
import { MONTH_NAMES, getCellColor, getValueColor, MOM_THRESHOLDS, DARK_THEME, TEXT_COLORS } from './chartConstants'
import { TableLegend, MOM_LEGEND_DEFAULT } from './ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface DualSeriesData {
  years: number[]
  monthlyData: Record<number, Record<number, { [key: string]: number | null } | null>>
}

interface MonthlyTableDualProps {
  /** テーブルデータ（年×月のマトリックス、各セルに2系列の値） */
  data: DualSeriesData
  /** 系列1のキー */
  series1Key: string
  /** 系列2のキー */
  series2Key: string
  /** 系列1の表示名 */
  series1Name: string
  /** 系列2の表示名 */
  series2Name: string
  /** 系列1のカラー */
  series1Color?: string
  /** 系列2のカラー */
  series2Color?: string
  /** 小数点以下の桁数 */
  decimals?: number
  /** 凡例を表示するかどうか */
  showLegend?: boolean
  /** ヘルパーテキストを表示するか */
  showHelperText?: boolean
  /** カスタムヘルパーテキスト */
  helperText?: string
}

// =============================================================================
// MonthlyTableDual コンポーネント
// =============================================================================

const DEFAULT_HELPER_TEXT = '※ 直近10年間の前月比データ（単位: %）'

export function MonthlyTableDual({
  data,
  series1Key,
  series2Key,
  series1Name,
  series2Name,
  series1Color = '#1890ff',
  series2Color = '#52c41a',
  decimals = 2,
  showLegend = true,
  showHelperText = true,
  helperText = DEFAULT_HELPER_TEXT,
}: MonthlyTableDualProps) {
  const thresholds = MOM_THRESHOLDS.default

  const formatValue = (value: number | null): string => {
    if (value === null || value === undefined) return '-'
    return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}`
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

      {/* 系列凡例 */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 12, fontSize: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span
            style={{
              display: 'inline-block',
              width: 12,
              height: 12,
              backgroundColor: series1Color,
              borderRadius: 2,
            }}
          />
          <span style={{ color: DARK_THEME.textSecondary }}>{series1Name}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span
            style={{
              display: 'inline-block',
              width: 12,
              height: 12,
              backgroundColor: series2Color,
              borderRadius: 2,
            }}
          />
          <span style={{ color: DARK_THEME.textSecondary }}>{series2Name}</span>
        </div>
      </div>

      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 11,
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
                  padding: '8px 2px',
                  borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                  fontWeight: 'bold',
                  minWidth: 70,
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
                const value1 = cellData ? cellData[series1Key] : null
                const value2 = cellData ? cellData[series2Key] : null
                const bgColor1 = getCellColor(value1, thresholds)
                const bgColor2 = getCellColor(value2, thresholds)
                const textColor1 = getValueColor(value1)
                const textColor2 = getValueColor(value2)

                return (
                  <td
                    key={month}
                    style={{
                      padding: '2px 2px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      verticalAlign: 'middle',
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      {/* 系列1 */}
                      <div
                        style={{
                          padding: '2px 4px',
                          backgroundColor: bgColor1,
                          borderRadius: 2,
                          borderLeft: `3px solid ${series1Color}`,
                        }}
                      >
                        <span style={{ color: value1 === null ? TEXT_COLORS.quaternary : textColor1, fontSize: 10 }}>
                          {formatValue(value1)}
                        </span>
                      </div>
                      {/* 系列2 */}
                      <div
                        style={{
                          padding: '2px 4px',
                          backgroundColor: bgColor2,
                          borderRadius: 2,
                          borderLeft: `3px solid ${series2Color}`,
                        }}
                      >
                        <span style={{ color: value2 === null ? TEXT_COLORS.quaternary : textColor2, fontSize: 10 }}>
                          {formatValue(value2)}
                        </span>
                      </div>
                    </div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {showLegend && <TableLegend items={MOM_LEGEND_DEFAULT} />}
    </div>
  )
}

export default MonthlyTableDual
