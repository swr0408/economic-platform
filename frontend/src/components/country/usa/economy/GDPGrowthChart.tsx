import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// Props型定義
interface GDPGrowthItem {
  date: string
  value: number
}

interface GDPGrowthChartProps {
  data: GDPGrowthItem[] | null
  nextRelease?: {
    date: string
    title: string
    estimate_type: string
    quarter: number
    year: number
  } | null
}

interface GDPChartData {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

type ViewMode = 'chart' | 'table'

// 四半期名の定義
const QUARTER_NAMES = ['Q1', 'Q2', 'Q3', 'Q4']

export default function GDPGrowthChart({ data, nextRelease }: GDPGrowthChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')
  const [viewMode, setViewMode] = useState<ViewMode>('chart')

  // propsのデータをチャート用に変換
  const gdpData = useMemo<GDPChartData[]>(() => {
    if (!data || data.length === 0) return []

    const chartData: GDPChartData[] = data.map((item) => ({
      date: item.date,
      value: item.value,
    }))

    // 日付でソート（古い順）
    chartData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return chartData
  }, [data])

  const formatPercentage = (value: number) => {
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(1)}%`
  }

  const formatQuarterLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    const year = date.getFullYear()
    const quarter = Math.floor(date.getMonth() / 3) + 1
    return `${year}Q${quarter}`
  }

  // 期間に基づいてデータをフィルタリング
  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all' || gdpData.length === 0) {
      return gdpData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      // デフォルトは2020年から
      cutoffDate.setFullYear(2020, 0, 1)
    } else {
      // 指定年数前から
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return gdpData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [gdpData, selectedPeriod])

  // テーブル用データ（年別×四半期のマトリックス）
  const tableData = useMemo(() => {
    if (gdpData.length === 0) return { years: [], quarterlyData: {} }

    // 直近10年分のデータを抽出
    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const quarterlyData: Record<number, Record<number, number | null>> = {}

    gdpData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const quarter = Math.floor(date.getMonth() / 3) // 0-3

      if (year >= startYear && year <= currentYear) {
        if (!quarterlyData[year]) {
          quarterlyData[year] = {}
        }
        quarterlyData[year][quarter] = item.value
      }
    })

    return { years, quarterlyData }
  }, [gdpData])

  const hasData = gdpData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="GDP成長率（前期比年率）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率（前期比年率）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // テーブルセルの背景色を決定
  const getCellColor = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'transparent'
    if (value > 3) return 'rgba(82, 196, 26, 0.3)'   // 強いプラス: 緑
    if (value > 1.5) return 'rgba(82, 196, 26, 0.15)' // プラス: 薄緑
    if (value > 0) return 'rgba(82, 196, 26, 0.05)'   // プラス: 緑
    if (value < -3) return 'rgba(255, 0, 0, 0.3)'   // マイナス: 赤
    if (value < -1.5) return 'rgba(255, 0, 0, 0.15)' // マイナス: 薄赤
    if (value < 0) return 'rgba(255, 0, 0, 0.05)'   // マイナス: 薄赤
    return 'transparent'
  }

  // 表示モード切り替えボタン
  const ViewModeButtons = () => (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
      <button
        onClick={() => setViewMode('chart')}
        style={{
          padding: '6px 12px',
          border: viewMode === 'chart' ? '2px solid #1890ff' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'chart' ? '#e6f7ff' : '#fff',
          cursor: 'pointer',
          fontWeight: viewMode === 'chart' ? 'bold' : 'normal',
        }}
      >
        グラフ
      </button>
      <button
        onClick={() => setViewMode('table')}
        style={{
          padding: '6px 12px',
          border: viewMode === 'table' ? '2px solid #1890ff' : '1px solid #d9d9d9',
          borderRadius: 4,
          background: viewMode === 'table' ? '#e6f7ff' : '#fff',
          cursor: 'pointer',
          fontWeight: viewMode === 'table' ? 'bold' : 'normal',
        }}
      >
        テーブル
      </button>
    </div>
  )

  // テーブルコンポーネント
  const GDPTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 13,
          textAlign: 'center',
        }}
      >
        <thead>
          <tr style={{ backgroundColor: '#fafafa' }}>
            <th style={{ padding: '10px 8px', borderBottom: '2px solid #d9d9d9', fontWeight: 'bold' }}>
              年
            </th>
            {QUARTER_NAMES.map((quarter, idx) => (
              <th
                key={idx}
                style={{
                  padding: '10px 8px',
                  borderBottom: '2px solid #d9d9d9',
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
          {tableData.years.map((year: number) => (
            <tr key={year}>
              <td
                style={{
                  padding: '8px',
                  borderBottom: '1px solid #e8e8e8',
                  fontWeight: 'bold',
                  backgroundColor: '#fafafa',
                }}
              >
                {year}
              </td>
              {Array.from({ length: 4 }, (_, quarter) => {
                const value = tableData.quarterlyData[year]?.[quarter]
                return (
                  <td
                    key={quarter}
                    style={{
                      padding: '8px',
                      borderBottom: '1px solid #e8e8e8',
                      backgroundColor: getCellColor(value),
                    }}
                  >
                    {value !== null && value !== undefined ? (
                      <span style={{ color: value >= 0 ? '#389e0d' : '#cf1322' }}>
                        {value >= 0 ? '+' : ''}{value.toFixed(1)}
                      </span>
                    ) : (
                      <span style={{ color: '#bfbfbf' }}>-</span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 8, fontSize: 11, color: '#888', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(82, 196, 26, 0.3)', marginRight: 4 }} />
          プラス（+2%以上）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(82, 196, 26, 0.15)', marginRight: 4 }} />
          プラス（0〜+2%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(255, 77, 79, 0.15)', marginRight: 4 }} />
          マイナス（0〜-2%）
        </span>
        <span>
          <span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: 'rgba(255, 77, 79, 0.3)', marginRight: 4 }} />
          マイナス（-2%以下）
        </span>
      </div>
    </div>
  )

  return (
    <div id="gdp-growth-chart">
      <ChartContainer
        title="GDP成長率（前期比年率）"
        showPeriodSelector={false}
        dataSource="BEA / FRED"
        sourceUrl="https://www.bea.gov/data/gdp/gross-domestic-product"
      >
        {/* 最新値表示 */}
        {latestValue && (
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 12,
              padding: '8px 12px',
              background: '#f5f5f5',
              borderRadius: 8,
            }}
          >
            <div>
              <span style={{ fontSize: 12, color: '#666' }}>最新値: </span>
              <span
                style={{
                  fontSize: 18,
                  fontWeight: 'bold',
                  color: latestValue.value >= 0 ? '#52c41a' : '#ff4d4f',
                }}
              >
                {formatPercentage(latestValue.value)}
              </span>
              <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>
                ({formatQuarterLabel(latestValue.date)})
              </span>
            </div>
            {nextRelease && (
              <div style={{ fontSize: 11, color: '#666', textAlign: 'right' }}>
                <div>次回発表: {nextRelease.date}</div>
                <div style={{ color: '#1890ff' }}>
                  Q{nextRelease.quarter}/{nextRelease.year} ({nextRelease.estimate_type})
                </div>
              </div>
            )}
          </div>
        )}

        <ViewModeButtons />

        {viewMode === 'chart' && (
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        )}
        {viewMode === 'table' && (
          <div style={{ fontSize: 11, color: '#888', marginBottom: 12 }}>
            ※ 直近10年間のGDP成長率データ（単位: %）
          </div>
        )}

        {viewMode === 'table' ? (
          <GDPTable />
        ) : (
          <ZoomableChart
            data={filteredData}
            dataKey="value"
            color="#1890ff"
            name="GDP成長率"
            height={450}
            tickFormatter={formatPercentage}
            tooltipFormatter={formatPercentage}
            tooltipLabelFormatter={formatQuarterLabel}
            xAxisTickFormatter={formatQuarterLabel}
            enableDynamicTicks={true}
            showZeroLine={true}
            showFiftyLine={false}
            connectNulls={true}
            hideLegend={true}
          />
        )}
      </ChartContainer>
    </div>
  )
}
