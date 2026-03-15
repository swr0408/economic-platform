import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import ChartContainer from '../../common/ChartContainer'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../../country/usa/common/chartConstants'

const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  gridLine: '#475569',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
  headerBg: '#1e3a5f',
  rowEvenBg: '#1e293b',
  rowOddBg: '#253547',
  rowHoverBg: '#334155',
}

interface NextRelease {
  date: string
  datetime_jst?: string
  time_jst?: string
  label?: string
  estimate?: number | null
}

interface IeaOmrResponse {
  headers: string[]
  rows: Record<string, string>[]
  next_release?: NextRelease | null
  metadata: {
    source: string
    file_name: string
    file_mtime: number | null
    row_count: number
    column_count: number
  }
  cached: boolean
  source: string
  last_updated: string | null
}


export default function IeaOilMarketReportChart() {
  const { data: response } = useQuery<IeaOmrResponse>({
    queryKey: ['iea-oil-market-report'],
    queryFn: async () => {
      const res = await axios.get('/api/market/iea-oil-market-report')
      return res.data
    },
    staleTime: 1000 * 60 * 5,
    refetchInterval: 1000 * 60 * 5,  // 5分ごとにポーリング（ファイル変更検出）
  })

  const headers = response?.headers ?? []
  const rows = response?.rows ?? []

  // 「項目」列は最初のヘッダー、残りがデータ列
  const itemHeader = headers[0] ?? '項目'
  const dataHeaders = headers.slice(1)

  return (
    <ChartContainer
      title="IEA Oil Market Report"
      dataSource="IEA"
      sourceUrl="https://www.iea.org/analysis?type=report&q=oil%20market%20report"
      showPeriodSelector={false}
    >
      {/* Latest info */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {response?.last_updated && (
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
              更新: {response.last_updated.slice(0, 16).replace('T', ' ')}
            </span>
          )}
        </div>
        {response?.next_release && (
          <span style={{ fontSize: 11, color: TEXT_COLORS.secondary, whiteSpace: 'nowrap' }}>
            次回: {response.next_release.date}
            {response.next_release.time_jst && ` ${response.next_release.time_jst} (JST)`}
          </span>
        )}
      </div>

      {/* Dynamic table */}
      {rows.length > 0 ? (
        <div style={{ overflowX: 'auto', marginTop: 8 }}>
          <table style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: 13,
            lineHeight: 1.6,
          }}>
            <thead>
              <tr>
                <th style={{
                  position: 'sticky',
                  left: 0,
                  zIndex: 2,
                  backgroundColor: DARK_THEME.headerBg,
                  color: DARK_THEME.textPrimary,
                  padding: '10px 14px',
                  textAlign: 'left',
                  fontWeight: 600,
                  borderBottom: `2px solid ${DARK_THEME.gridLine}`,
                  whiteSpace: 'nowrap',
                  minWidth: 200,
                }}>
                  {itemHeader}
                </th>
                {dataHeaders.map((header) => (
                  <th key={header} style={{
                    backgroundColor: DARK_THEME.headerBg,
                    color: DARK_THEME.textPrimary,
                    padding: '10px 14px',
                    textAlign: 'left',
                    fontWeight: 600,
                    borderBottom: `2px solid ${DARK_THEME.gridLine}`,
                    whiteSpace: 'nowrap',
                    minWidth: 140,
                  }}>
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIdx) => (
                <tr
                  key={rowIdx}
                  style={{
                    backgroundColor: rowIdx % 2 === 0 ? DARK_THEME.rowEvenBg : DARK_THEME.rowOddBg,
                    transition: 'background-color 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = DARK_THEME.rowHoverBg }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = rowIdx % 2 === 0 ? DARK_THEME.rowEvenBg : DARK_THEME.rowOddBg }}
                >
                  <td style={{
                    position: 'sticky',
                    left: 0,
                    zIndex: 1,
                    backgroundColor: 'inherit',
                    padding: '8px 14px',
                    fontWeight: 600,
                    color: DARK_THEME.textPrimary,
                    borderBottom: `1px solid ${DARK_THEME.gridLine}`,
                    whiteSpace: 'nowrap',
                  }}>
                    {row[itemHeader] ?? ''}
                  </td>
                  {dataHeaders.map((header) => {
                    const value = row[header] ?? ''
                    // 差分列の色分け（+/= で始まるもの）
                    let cellColor = DARK_THEME.textSecondary
                    if (value.startsWith('+') || value.startsWith('=+')) {
                      cellColor = '#4ade80'  // green
                    } else if (value.startsWith('-') || value.startsWith('=-')) {
                      cellColor = '#f87171'  // red
                    }

                    return (
                      <td key={header} style={{
                        padding: '8px 14px',
                        color: cellColor,
                        borderBottom: `1px solid ${DARK_THEME.gridLine}`,
                        whiteSpace: 'pre-wrap',
                        maxWidth: 350,
                      }}>
                        {value || '—'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データが利用できません
        </div>
      )}
    </ChartContainer>
  )
}
