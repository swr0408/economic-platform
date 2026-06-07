/**
 * 出生地別労働者数チャートコンポーネント
 *
 * FRED データを使用して出生地別の労働力人口・雇用者数を表示
 * - 労働力人口（国内生まれ: LNU01073395）/ 労働力人口（海外生まれ: LNU01073413）
 * - 雇用者数（国内生まれ: LNU02073395）/ 雇用者数（海外生まれ: LNU02073413）
 *
 * スケールが大きく異なるため、国内生まれは左Y軸、海外生まれは右Y軸で表示
 *
 * 表示モード:
 * - 現数値（レベル）- 左右Y軸で4系列同時表示
 * - 前月増減幅グラフ - DataType切替で1系列ずつ表示
 * - 前月増減幅テーブル - DataType切替で1系列ずつ表示
 *
 * 発表スケジュール: BLS Employment Situation（毎月第1金曜日 8:30 ET）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import {
  ComposedChart,
  Line,
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
import type { NumberOfWorkersByPlaceOfBirthData } from '../../../../hooks/useDashboardData'

import {
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  VALUE_CHANGE_DATA_KIND_OPTIONS,
  type ValueChangeDataKind,
  DISPLAY_MODE_OPTIONS,
  type DisplayMode,
  CHANGE_LEGEND_100K,
  getChangeCellColor100k,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMultiValueMonthlyTableData,
  formatDateLabel,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  ChangeTooltip,
  ValueTooltip,
} from '../common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../common/MonthlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface NumberOfWorkersByPlaceOfBirthChartProps {
  data: NumberOfWorkersByPlaceOfBirthData | null
}

type SeriesKey = 'labor_force_native' | 'labor_force_foreign' | 'employment_native' | 'employment_foreign'

const DATA_TYPE_OPTIONS: { type: SeriesKey; label: string }[] = [
  { type: 'labor_force_native', label: '労働力人口（国内）' },
  { type: 'labor_force_foreign', label: '労働力人口（海外）' },
  { type: 'employment_native', label: '雇用者数（国内）' },
  { type: 'employment_foreign', label: '雇用者数（海外）' },
]

const DEFAULT_COLORS: Record<SeriesKey, string> = {
  labor_force_native: '#1890ff',
  labor_force_foreign: '#fa8c16',
  employment_native: '#52c41a',
  employment_foreign: '#eb2f96',
}

const SERIES_NAMES: Record<SeriesKey, string> = {
  labor_force_native: '労働力人口（国内生まれ）',
  labor_force_foreign: '労働力人口（海外生まれ）',
  employment_native: '雇用者数（国内生まれ）',
  employment_foreign: '雇用者数（海外生まれ）',
}

// 国内生まれ系列（左Y軸）
const NATIVE_KEYS: SeriesKey[] = ['labor_force_native', 'employment_native']
// 海外生まれ系列（右Y軸）
const FOREIGN_KEYS: SeriesKey[] = ['labor_force_foreign', 'employment_foreign']

type ChangeKey = `${SeriesKey}_change`

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NumberOfWorkersByPlaceOfBirthChart({ data }: NumberOfWorkersByPlaceOfBirthChartProps) {
  const [dataKind, setDataKind] = useState<ValueChangeDataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<SeriesKey>('labor_force_native')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { handleLegendClick, isHidden } = useHiddenSeries<SeriesKey | ChangeKey>()

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 10,
    change: 3,
  })

  const sortedData = useSortedData(data?.data)

  // 前月増減幅を計算
  const chartData = useMemo(() => {
    if (sortedData.length === 0) return []
    return sortedData.map((item, index) => {
      const prevItem = index > 0 ? sortedData[index - 1] : null
      const calcChange = (key: SeriesKey): number | null => {
        const curr = item[key]
        const prev = prevItem ? prevItem[key] : null
        return prev !== null && prev !== undefined && curr !== null && curr !== undefined
          ? Math.round(curr - prev)
          : null
      }
      return {
        ...item,
        labor_force_native_change: calcChange('labor_force_native'),
        labor_force_foreign_change: calcChange('labor_force_foreign'),
        employment_native_change: calcChange('employment_native'),
        employment_foreign_change: calcChange('employment_foreign'),
      }
    })
  }, [sortedData])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ
  const changeTableData = useMultiValueMonthlyTableData(
    chartData,
    {
      labor_force_native: (item) => item.labor_force_native_change,
      labor_force_foreign: (item) => item.labor_force_foreign_change,
      employment_native: (item) => item.employment_native_change,
      employment_foreign: (item) => item.employment_foreign_change,
    },
    10
  )

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="出生地別労働者数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="出生地別労働者数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release
  const seriesConfig = data.series_config || {}

  const getColor = (key: SeriesKey): string => {
    return seriesConfig[key]?.color || DEFAULT_COLORS[key]
  }

  const latestChange = chartData.length >= 2 ? chartData[chartData.length - 1] : null

  const getLatestItems = () => {
    if (dataKind === 'value') {
      if (!latest) return []
      return (Object.keys(SERIES_NAMES) as SeriesKey[]).map((key) => ({
        label: SERIES_NAMES[key],
        value: latest[key],
        color: getColor(key),
        format: 'number' as const,
        unit: 'k',
        decimals: 0,
      }))
    }
    // 前月増減幅モード
    if (!latestChange) return []
    return (Object.keys(SERIES_NAMES) as SeriesKey[]).map((key) => {
      const changeKey = `${key}_change` as keyof typeof latestChange
      const change = latestChange[changeKey] as number | null
      return {
        label: `${SERIES_NAMES[key]}（増減）`,
        value: change !== null ? `${change >= 0 ? '+' : ''}${change.toLocaleString()}k` : 'N/A',
        color: change !== null && change >= 0 ? '#52c41a' : '#ff4d4f',
      }
    })
  }

  return (
    <div id="workers-by-place-of-birth">
      <ChartContainer
        title="出生地別労働者数"
        showPeriodSelector={false}
        dataSource="FRED / BLS"
        sourceUrl="https://www.bls.gov/news.release/empsit.toc.htm"
        handbookId="workers-by-place-of-birth"
      >
        <LatestValueBox
          items={getLatestItems()}
          date={latestChange?.date || latest?.date}
          nextRelease={nextRelease}
        />

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 現数値 / 前月増減幅 切替 */}
                  <ViewModeButtonGroup options={VALUE_CHANGE_DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />

                  {/* 表示形式切替（増減幅のときのみ） */}
                  {dataKind === 'change' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 現数値グラフ（左右Y軸で4系列同時表示） */}
                  {dataKind === 'value' && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <AntTooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open('/compare?s=workers_labor_force_native&s=workers_labor_force_foreign&s=workers_employment_native&s=workers_employment_foreign', '_blank')}
                          >
                            データ比較
                          </Button>
                        </AntTooltip>
                      </div>
                      <ResponsiveContainer width="100%" height={450}>
                        <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                          <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                          <XAxis
                            dataKey="date"
                            tickFormatter={formatDateLabel}
                            tick={AXIS_STYLE.tick}
                            interval={AXIS_STYLE.interval}
                          />
                          {/* 左Y軸: 国内生まれ */}
                          <YAxis
                            yAxisId="left"
                            domain={['dataMin - 2000', 'dataMax + 2000']}
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v) => `${v.toLocaleString()}`}
                            label={{
                              value: '国内生まれ（k）',
                              angle: -90,
                              position: 'insideLeft',
                              style: { fontSize: 11, fill: getColor('labor_force_native') }
                            }}
                          />
                          {/* 右Y軸: 海外生まれ */}
                          <YAxis
                            yAxisId="right"
                            orientation="right"
                            domain={['dataMin - 1000', 'dataMax + 1000']}
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v) => `${v.toLocaleString()}`}
                            label={{
                              value: '海外生まれ（k）',
                              angle: 90,
                              position: 'insideRight',
                              style: { fontSize: 11, fill: getColor('labor_force_foreign') }
                            }}
                          />
                          <Tooltip content={<ValueTooltip unit="k" />} />
                          <Legend
                            onClick={(e) => handleLegendClick(e.dataKey as SeriesKey)}
                            wrapperStyle={{ cursor: 'pointer' }}
                          />
                          {NATIVE_KEYS.map((key) => (
                            <Line
                              key={key}
                              yAxisId="left"
                              type="monotone"
                              dataKey={key}
                              stroke={getColor(key)}
                              strokeWidth={2}
                              dot={false}
                              name={SERIES_NAMES[key]}
                              hide={isHidden(key)}
                              isAnimationActive={false}
                              connectNulls={true}
                            />
                          ))}
                          {FOREIGN_KEYS.map((key) => (
                            <Line
                              key={key}
                              yAxisId="right"
                              type="monotone"
                              dataKey={key}
                              stroke={getColor(key)}
                              strokeWidth={2}
                              strokeDasharray="4 3"
                              dot={false}
                              name={SERIES_NAMES[key]}
                              hide={isHidden(key)}
                              isAnimationActive={false}
                              connectNulls={true}
                            />
                          ))}
                        </ComposedChart>
                      </ResponsiveContainer>
                    </>
                  )}

                  {/* 前月増減幅グラフ */}
                  {dataKind === 'change' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup
                        options={DATA_TYPE_OPTIONS}
                        currentType={dataType}
                        onChange={setDataType}
                      />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <ResponsiveContainer width="100%" height={450}>
                        <ComposedChart data={filteredData} margin={CHART_MARGIN}>
                          <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                          <XAxis
                            dataKey="date"
                            tickFormatter={formatDateLabel}
                            tick={AXIS_STYLE.tick}
                            interval={AXIS_STYLE.interval}
                          />
                          <YAxis
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toLocaleString()}`}
                            domain={['dataMin - 50', 'dataMax + 50']}
                            label={{
                              value: '増減（k）',
                              angle: -90,
                              position: 'insideLeft',
                              dy: 20,
                              style: { fontSize: 11, fill: '#666' }
                            }}
                          />
                          <Tooltip content={<ChangeTooltip unit="k" formatValue={(v) => v.toLocaleString()} />} />
                          <Legend />
                          <ReferenceLine y={0} stroke="#000" strokeWidth={1} />
                          <Bar
                            dataKey={`${dataType}_change`}
                            fill={getColor(dataType)}
                            name={`${SERIES_NAMES[dataType]}（増減）`}
                            isAnimationActive={false}
                          />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </>
                  )}

                  {/* 前月増減幅テーブル */}
                  {dataKind === 'change' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={changeTableData}
                      dataTypes={DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                      helperText="※ 直近10年間の前月増減幅データ（単位: 千人）"
                      formatValue={(value) => {
                        if (value === null) return '-'
                        return `${value >= 0 ? '+' : ''}${value.toLocaleString()}`
                      }}
                      getCellBgColor={getChangeCellColor100k}
                      legendItems={CHANGE_LEGEND_100K}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nonfarm_payrolls" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
