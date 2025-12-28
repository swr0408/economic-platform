/**
 * 小売売上高チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { RetailSalesData, RetailControlData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  MONTH_NAMES,
  getCellColor,
  DARK_THEME,
  TEXT_COLORS,
} from '../common/chartConstants'
import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
} from '../common/useChartData'
import {
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  NoDataMessage,
  TableLegend,
  MOM_LEGEND_DEFAULT,
  LatestValueBox,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface RetailSalesChartProps {
  data: RetailSalesData | null
  controlData: RetailControlData | null
}

type ViewMode = 'yoy' | 'mom_table' | 'mom_chart'
type DataType = 'total' | 'ex_auto' | 'control_group'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom_table', label: '前月比テーブル' },
  { mode: 'mom_chart', label: '前月比グラフ' },
]

// データタイプ設定
const DATA_TYPE_OPTIONS: { type: DataType; label: string }[] = [
  { type: 'total', label: '総合' },
  { type: 'ex_auto', label: '自動車除く' },
  { type: 'control_group', label: 'コントロールグループ' },
]

// カラー設定
const COLORS = {
  yoy: CHART_COLORS.positive,
  yoy_ex: CHART_COLORS.purple,
  yoy_cg: CHART_COLORS.cyan,
  mom: CHART_COLORS.positive,
  mom_ex: CHART_COLORS.purple,
  mom_cg: CHART_COLORS.cyan,
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function RetailSalesChart({ data, controlData }: RetailSalesChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [dataType, setDataType] = useState<DataType>('total')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理（共通フック使用）
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    yoy: 'default',
    mom_table: 'default',
    mom_chart: 3,
  })

  // コントロールグループデータを日付でマッピング
  const controlGroupMap = useMemo(() => {
    if (!controlData?.data) return new Map<string, number>()
    const map = new Map<string, number>()
    controlData.data.forEach((item) => {
      map.set(item.date, item.mom)
    })
    return map
  }, [controlData])

  // データを日付昇順にソートし、コントロールグループの前月比をマージ
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        ...item,
        control_group_mom: controlGroupMap.get(item.date) ?? null,
      }))
  }, [data, controlGroupMap])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const momTableData = useMemo(() => {
    if (chartData.length === 0) return { years: [] as number[], monthlyData: {} as Record<number, Record<number, { total: number | null; ex_auto: number | null; control_group: number | null }>> }

    const currentYear = new Date().getFullYear()
    const startYear = currentYear - 9
    const years: number[] = []
    for (let y = startYear; y <= currentYear; y++) {
      years.push(y)
    }

    const monthlyData: Record<number, Record<number, { total: number | null; ex_auto: number | null; control_group: number | null }>> = {}

    chartData.forEach((item) => {
      const date = new Date(item.date)
      const year = date.getFullYear()
      const month = date.getMonth()

      if (year >= startYear && year <= currentYear) {
        if (!monthlyData[year]) {
          monthlyData[year] = {}
        }
        monthlyData[year][month] = {
          total: item.mom,
          ex_auto: item.ex_auto_mom,
          control_group: item.control_group_mom
        }
      }
    })

    return { years, monthlyData }
  }, [chartData])

  const hasData = chartData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="小売売上高（Retail Sales）" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="小売売上高（Retail Sales）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  // 前月比テーブルコンポーネント（ダークテーマ）
  const MoMTable = () => (
    <div style={{ overflowX: 'auto' }}>
      <DataTypeButtonGroup
        options={DATA_TYPE_OPTIONS}
        currentType={dataType}
        onChange={setDataType}
      />
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'center', color: DARK_THEME.textPrimary }}>
        <thead>
          <tr style={{ backgroundColor: DARK_THEME.bgTertiary }}>
            <th style={{ padding: '8px 4px', borderBottom: `2px solid ${DARK_THEME.borderLight}`, fontWeight: 'bold' }}>年</th>
            {MONTH_NAMES.map((month, idx) => (
              <th key={idx} style={{ padding: '8px 4px', borderBottom: `2px solid ${DARK_THEME.borderLight}`, fontWeight: 'bold', minWidth: 50 }}>
                {month}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {momTableData.years.map((year: number) => (
            <tr key={year}>
              <td style={{ padding: '6px 4px', borderBottom: `1px solid ${DARK_THEME.border}`, fontWeight: 'bold', backgroundColor: DARK_THEME.bgTertiary }}>
                {year}
              </td>
              {Array.from({ length: 12 }, (_, month) => {
                const cellData = momTableData.monthlyData[year]?.[month]
                let value: number | null | undefined
                if (dataType === 'total') value = cellData?.total
                else if (dataType === 'ex_auto') value = cellData?.ex_auto
                else value = cellData?.control_group

                return (
                  <td key={month} style={{ padding: '6px 4px', borderBottom: `1px solid ${DARK_THEME.border}`, backgroundColor: getCellColor(value) }}>
                    {value !== null && value !== undefined ? (
                      <span style={{ color: value >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative }}>
                        {value >= 0 ? '+' : ''}{value.toFixed(2)}
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
      <TableLegend items={MOM_LEGEND_DEFAULT} />
    </div>
  )

  return (
    <div id="retail-sales">
      <ChartContainer
        title="小売売上高"
        showPeriodSelector={false}
        dataSource="FRED (Census Bureau)"
        sourceUrl="https://www.census.gov/retail/index.html"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '総合',
              value: viewMode === 'yoy' ? latest?.yoy : latest?.mom,
              color: COLORS.yoy,
              format: 'percent',
            },
            {
              label: '自動車除く',
              value: viewMode === 'yoy' ? latest?.ex_auto_yoy : latest?.ex_auto_mom,
              color: COLORS.yoy_ex,
              format: 'percent',
            },
            ...(viewMode !== 'yoy' && controlData?.latest
              ? [{
                  label: 'コントロールグループ',
                  value: controlData.latest.mom,
                  color: COLORS.yoy_cg,
                  format: 'percent' as const,
                }]
              : []),
          ]}
          date={latest?.date}
          nextRelease={data.next_release}
        />

        <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

        {/* 前年比グラフ */}
        {viewMode === 'yoy' && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredData}
              lines={[
                { dataKey: 'yoy', color: COLORS.yoy, name: '小売売上高（前年比）', hide: hiddenSeries.has('yoy') },
                { dataKey: 'ex_auto_yoy', color: COLORS.yoy_ex, name: '自動車除く（前年比）', hide: hiddenSeries.has('ex_auto_yoy') },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 3', 'dataMax + 3']}
              onLegendClick={handleLegendClick}
            />
          </>
        )}

        {/* 前月比テーブル */}
        {viewMode === 'mom_table' && <MoMTable />}

        {/* 前月比グラフ */}
        {viewMode === 'mom_chart' && (
          <>
            <DataTypeButtonGroup options={DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardBarChart
              data={filteredData}
              bars={[
                dataType === 'total'
                  ? { dataKey: 'mom', color: COLORS.mom, name: '小売売上高（前月比）' }
                  : dataType === 'ex_auto'
                  ? { dataKey: 'ex_auto_mom', color: COLORS.mom_ex, name: '自動車除く（前月比）' }
                  : { dataKey: 'control_group_mom', color: COLORS.mom_cg, name: 'コントロールグループ（前月比）' },
              ]}
              yAxisFormatter={(v) => `${v}%`}
              yDomain={['dataMin - 1', 'dataMax + 1']}
            />
          </>
        )}
      </ChartContainer>
    </div>
  )
}
