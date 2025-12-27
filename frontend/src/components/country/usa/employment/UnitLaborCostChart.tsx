/**
 * 単位労働コスト / 労働生産性チャートコンポーネント
 *
 * FRED データを使用:
 * - PRS85006112: 単位労働コスト（前期比）
 * - PRS85006092: 労働生産性（前期比）
 *
 * 表示モード:
 * - 前期比テーブル（タブ切り替え）
 * - 前期比グラフ（両方棒グラフ）
 *
 * 四半期ごと発表（2月、3月、5月、6月、8月、9月、11月、12月）8:30 ET
 *
 * 共通コンポーネントを使用
 */
import { useState, useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { UnitLaborCostData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  TOOLTIP_STYLE,
  QUARTER_NAMES,
  getValueColor,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  formatQuarterLabel,
  formatQuarterLabelJP,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ViewModeButtonGroup,
  TableLegend,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface UnitLaborCostChartProps {
  data: UnitLaborCostData | null
}

type ViewMode = 'qoq_table' | 'qoq_chart'
type TableType = 'ulc' | 'productivity'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'qoq_table', label: '前期比テーブル' },
  { mode: 'qoq_chart', label: '前期比グラフ' },
]

// テーブルタイプ設定
const TABLE_TYPE_OPTIONS: { type: TableType; label: string }[] = [
  { type: 'ulc', label: '単位労働コスト' },
  { type: 'productivity', label: '労働生産性' },
]

// カラー設定
const COLORS = {
  ulc: '#ff4d4f',         // 単位労働コスト - 赤
  productivity: '#1890ff', // 労働生産性 - 青
}

// 系列名（日本語）
const SERIES_NAMES = {
  ulc: '単位労働コスト',
  productivity: '労働生産性',
}

// 前期比テーブルの凡例（単位：%）
const CHANGE_LEGEND = [
  { color: 'rgba(82, 196, 26, 0.3)', label: '+1.0%以上' },
  { color: 'rgba(82, 196, 26, 0.15)', label: '0〜+1.0%' },
  { color: 'rgba(255, 77, 79, 0.15)', label: '0〜-1.0%' },
  { color: 'rgba(255, 77, 79, 0.3)', label: '-1.0%以下' },
]

// ULC用の閾値
const ULC_THRESHOLDS = {
  high: 1.0,
  low: -1.0,
}

// =============================================================================
// ヘルパー関数
// =============================================================================

/** ULC用のセル背景色を取得 */
function getULCCellColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'transparent'
  if (value > ULC_THRESHOLDS.high) return 'rgba(82, 196, 26, 0.3)'
  if (value > 0) return 'rgba(82, 196, 26, 0.15)'
  if (value < ULC_THRESHOLDS.low) return 'rgba(255, 77, 79, 0.3)'
  if (value < 0) return 'rgba(255, 77, 79, 0.15)'
  return 'transparent'
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

interface TooltipPayload {
  name: string
  value: number
  color: string
  dataKey: string
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string
  unit?: string
}

function ChangeTooltip({ active, payload, label, unit = '%' }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatQuarterLabelJP(label || '')}
      </div>
      {payload.map((item, index) => {
        const value = item.value
        const sign = value >= 0 ? '+' : ''
        return (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
              fontSize: 13,
              padding: '4px 12px',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16 }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  backgroundColor: item.color,
                  marginRight: 6,
                }}
              />
              {item.name}
            </span>
            <span style={{ fontWeight: 500, color: value >= 0 ? '#52c41a' : '#ff4d4f' }}>
              {sign}{value.toFixed(1)}{unit}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// 四半期テーブルコンポーネント（タブ切り替え対応）
// =============================================================================

interface QuarterlyTableData {
  years: number[]
  quarterlyData: Record<number, Record<number, { ulc: number | null; productivity: number | null }>>
}

interface QuarterlyTableProps {
  data: QuarterlyTableData
  selectedType: TableType
  onTypeChange: (type: TableType) => void
  decimals?: number
  helperText?: string
}

function QuarterlyTable({
  data,
  selectedType,
  onTypeChange,
  decimals = 1,
  helperText = '※ 直近10年間の前期比データ（単位: %）',
}: QuarterlyTableProps) {
  // フォーマット関数
  const formatValue = (value: number | null): string => {
    if (value === null || value === undefined) return '-'
    return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}`
  }

  if (data.years.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
        データがありません
      </div>
    )
  }

  // タブ切り替えボタンのスタイル
  const getTabButtonStyle = (type: TableType, isActive: boolean) => ({
    padding: '6px 16px',
    border: isActive ? `2px solid ${COLORS[type]}` : '1px solid #d9d9d9',
    borderRadius: 4,
    background: isActive ? (type === 'ulc' ? '#fff1f0' : '#e6f7ff') : '#fff',
    cursor: 'pointer',
    fontWeight: isActive ? 'bold' as const : 'normal' as const,
    color: isActive ? COLORS[type] : '#333',
    fontSize: 13,
  })

  return (
    <div style={{ overflowX: 'auto' }}>
      {/* タブ切り替えボタン */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {TABLE_TYPE_OPTIONS.map((option) => (
          <button
            key={option.type}
            onClick={() => onTypeChange(option.type)}
            style={getTabButtonStyle(option.type, selectedType === option.type)}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div style={{ fontSize: 11, color: '#888', marginBottom: 12 }}>
        {helperText}
      </div>

      {/* 選択されたテーブル */}
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 12,
          textAlign: 'center',
        }}
      >
        <thead>
          <tr style={{ backgroundColor: '#fafafa' }}>
            <th
              style={{
                padding: '8px 4px',
                borderBottom: '2px solid #d9d9d9',
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
          {data.years.map((year) => (
            <tr key={year}>
              <td
                style={{
                  padding: '6px 4px',
                  borderBottom: '1px solid #e8e8e8',
                  fontWeight: 'bold',
                  backgroundColor: '#fafafa',
                }}
              >
                {year}
              </td>
              {Array.from({ length: 4 }, (_, quarter) => {
                const cellData = data.quarterlyData[year]?.[quarter]
                const value = selectedType === 'ulc' ? (cellData?.ulc ?? null) : (cellData?.productivity ?? null)
                const displayValue = formatValue(value)
                const bgColor = getULCCellColor(value)
                const textColor = getValueColor(value)

                return (
                  <td
                    key={quarter}
                    style={{
                      padding: '6px 4px',
                      borderBottom: '1px solid #e8e8e8',
                      backgroundColor: bgColor,
                    }}
                  >
                    <span style={{ color: value === null ? '#bfbfbf' : textColor }}>
                      {displayValue}
                    </span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <TableLegend items={CHANGE_LEGEND} />
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function UnitLaborCostChart({ data }: UnitLaborCostChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('qoq_table')
  const [tableType, setTableType] = useState<TableType>('ulc')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    qoq_chart: 5,
    qoq_table: 'default',
  })

  // データのソート
  const sortedData = useSortedData(data?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 四半期テーブルデータの生成
  const tableData = useMemo(() => {
    if (sortedData.length === 0) return { years: [], quarterlyData: {} }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9

    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const quarterlyData: Record<number, Record<number, { ulc: number | null; productivity: number | null }>> = {}

    sortedData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const quarter = Math.floor(date.getMonth() / 3)

      if (year >= startYear && year <= currentYear) {
        if (!quarterlyData[year]) {
          quarterlyData[year] = {}
        }
        quarterlyData[year][quarter] = {
          ulc: item.ulc_pch ?? null,
          productivity: item.productivity_pch ?? null,
        }
      }
    })

    return { years, quarterlyData }
  }, [sortedData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="単位労働コスト / 労働生産性" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="単位労働コスト / 労働生産性" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    return [
      {
        label: SERIES_NAMES.ulc,
        value: latest.ulc_pch !== null ? `${latest.ulc_pch >= 0 ? '+' : ''}${latest.ulc_pch.toFixed(1)}%` : 'N/A',
        color: latest.ulc_pch !== null && latest.ulc_pch >= 0 ? CHART_COLORS.negative : CHART_COLORS.positive,
      },
      {
        label: SERIES_NAMES.productivity,
        value: latest.productivity_pch !== null ? `${latest.productivity_pch >= 0 ? '+' : ''}${latest.productivity_pch.toFixed(1)}%` : 'N/A',
        color: latest.productivity_pch !== null && latest.productivity_pch >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
      },
    ]
  }

  return (
    <div id="unit-labor-cost">
      <ChartContainer
        title="単位労働コスト / 労働生産性"
        showPeriodSelector={false}
        dataSource="FRED - BLS"
        sourceUrl="https://www.bls.gov/news.release/prod2.toc.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
          dateFormatter={formatQuarterLabel}
        />

        {/* ビューモード切り替え */}
        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 前期比グラフ（両方棒グラフ） */}
        {viewMode === 'qoq_chart' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <ResponsiveContainer width="100%" height={450}>
              <BarChart data={filteredData} margin={CHART_MARGIN} barCategoryGap="20%">
                <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatQuarterLabel}
                  tick={AXIS_STYLE.tick}
                  interval={AXIS_STYLE.interval}
                />
                <YAxis
                  tick={AXIS_STYLE.tick}
                  tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
                  domain={['dataMin - 1', 'dataMax + 1']}
                  label={{
                    angle: -90,
                    position: 'insideLeft',
                    dy: 20,
                    style: { fontSize: 11, fill: '#666' }
                  }}
                />
                <Tooltip content={<ChangeTooltip />} />
                <Legend onClick={(e) => handleLegendClick(e.dataKey as string)} />
                <ReferenceLine y={0} stroke="#000" strokeWidth={1} />

                <Bar
                  dataKey="ulc_pch"
                  fill={COLORS.ulc}
                  name={SERIES_NAMES.ulc}
                  hide={hiddenSeries.has('ulc_pch')}
                />
                <Bar
                  dataKey="productivity_pch"
                  fill={COLORS.productivity}
                  name={SERIES_NAMES.productivity}
                  hide={hiddenSeries.has('productivity_pch')}
                />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}

        {/* 前期比テーブル（タブ切り替え） */}
        {viewMode === 'qoq_table' && (
          <QuarterlyTable
            data={tableData}
            selectedType={tableType}
            onTypeChange={setTableType}
          />
        )}
      </ChartContainer>
    </div>
  )
}
