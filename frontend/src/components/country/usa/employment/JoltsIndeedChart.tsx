/**
 * JOLTS求人 / Indeed求人件数チャートコンポーネント
 *
 * FRED データを使用して表示
 * - JOLTS求人件数（JTSJOL）- 左Y軸（千人）
 * - Indeed求人件数指数（IHLIDXUS）- 右Y軸（2020年2月1日=100）
 *
 * 表示モード:
 * - 現数値（レベル）- IndeedのスケールをJOLTSに合わせて表示
 * - JOLTS前月増減幅グラフ（Indeedは追加しない）
 * - JOLTS前月増減幅テーブル（Indeedは追加しない）
 *
 * 共通コンポーネントを使用
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
import type { JoltsIndeedData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  CHART_COLORS,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  TOOLTIP_STYLE,
  CHANGE_LEGEND_200K,
  getChangeCellColor200k,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  formatDateLabel,
  formatDateLabelJP,
  useHiddenSeries,
} from '../common/useChartData'
import {
  LatestValueBox,
  NoDataMessage,
  ViewModeButtonGroup,
  ChangeTooltip,
} from '../common/ChartComponents'
import { MonthlyTable } from '../common/MonthlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface JoltsIndeedChartProps {
  data: JoltsIndeedData | null
}

type ViewMode = 'value' | 'jolts_change_chart' | 'jolts_change_table'

// ビューモード設定
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'jolts_change_table', label: 'JOLTS前月増減幅テーブル' },
  { mode: 'jolts_change_chart', label: 'JOLTS前月増減幅グラフ' },
]

// カラー設定（サービスから取得したものを優先、フォールバック用）
const DEFAULT_COLORS = {
  jolts: CHART_COLORS.primary,     // 青（左軸）
  indeed: CHART_COLORS.orange,     // オレンジ（右軸）
}

// 系列名（日本語）
const SERIES_NAMES = {
  jolts: 'JOLTS求人件数',
  indeed: 'Indeed求人件数指数（1M遅行）',
}


// =============================================================================
// カスタムツールチップ
// =============================================================================

interface ScaledDataItem {
  date: string
  jolts: number | null
  indeed: number | null
  indeedShifted: number | null  // 1ヶ月シフト後のIndeed値
  indeedScaled: number | null   // JOLTSスケールに変換後の値
  jolts_change: number | null   // JOLTS前月増減幅
}

interface TooltipPayload {
  name: string
  value: number
  color: string
  dataKey: string
  payload: ScaledDataItem
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string
}

function ValueTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, padding: '8px 12px' }}>
        {formatDateLabelJP(label || '')}
      </div>
      {payload.map((item, index) => {
        // JOLTSは千人単位、Indeedは指数（シフト後の値を使用）
        const isJolts = item.dataKey === 'jolts'
        const isIndeed = item.dataKey === 'indeedScaled'
        let displayValue: string
        if (isJolts) {
          displayValue = `${item.value.toLocaleString()}k`
        } else if (isIndeed) {
          // indeedScaledの場合はシフト後のindeed値を表示
          const shiftedIndeed = item.payload?.indeedShifted
          displayValue = shiftedIndeed !== null && shiftedIndeed !== undefined
            ? shiftedIndeed.toFixed(1)
            : '-'
        } else {
          displayValue = item.value.toFixed(1)
        }
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
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
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
            <span style={{ fontWeight: 500, color: item.color }}>
              {displayValue}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function JoltsIndeedChart({ data }: JoltsIndeedChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { handleLegendClick, isHidden } = useHiddenSeries<'jolts' | 'indeed' | 'jolts_change'>()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 'default',
    jolts_change_chart: 3,
    jolts_change_table: 'default',
  })

  // データのソート
  const sortedData = useSortedData(data?.data)

  const hasData = sortedData.length > 0

  // 全データに対してIndeedシフトとJOLTS増減幅を計算（期間フィルタ前に計算）
  const fullChartData = useMemo(() => {
    if (sortedData.length === 0) return []

    // Indeedの値を日付でマップ化（1ヶ月シフト用）
    const indeedByDate = new Map<string, number | null>()
    sortedData.forEach(d => {
      if (d.indeed !== null) {
        const date = new Date(d.date)
        date.setMonth(date.getMonth() - 1)
        const shiftedDate = date.toISOString().slice(0, 10)
        indeedByDate.set(shiftedDate, d.indeed)
      }
    })

    // JOLTSデータのみを抽出して前月値をマップ化（月次データは月の1日で記録）
    const joltsDataByMonth = new Map<string, number>()
    sortedData.forEach(d => {
      if (d.jolts !== null) {
        // YYYY-MM形式でキー化
        const monthKey = d.date.slice(0, 7)
        joltsDataByMonth.set(monthKey, d.jolts)
      }
    })

    // シフトしたIndeed値と増減幅を計算
    return sortedData.map((d) => {
      const indeedShifted = indeedByDate.get(d.date) ?? null

      // JOLTS増減幅は、JOLTSデータがある場合のみ計算
      let jolts_change: number | null = null
      if (d.jolts !== null) {
        // 前月のJOLTS値を探す
        const currentDate = new Date(d.date)
        currentDate.setMonth(currentDate.getMonth() - 1)
        const prevMonthKey = `${currentDate.getFullYear()}-${String(currentDate.getMonth() + 1).padStart(2, '0')}`
        const prevJolts = joltsDataByMonth.get(prevMonthKey)
        if (prevJolts !== undefined) {
          jolts_change = Math.round(d.jolts - prevJolts)
        }
      }

      return {
        ...d,
        indeedShifted,
        jolts_change,
      }
    })
  }, [sortedData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(fullChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // JOLTS前月増減幅グラフ用データ（JOLTSデータのみ）
  const joltsChangeData = useMemo(() => {
    return filteredData.filter(d => d.jolts !== null)
  }, [filteredData])

  // スケーリング計算（フィルタ後のデータに対して）
  const { scaledData, joltsMin, joltsMax, indeedMin, indeedMax } = useMemo(() => {
    if (filteredData.length === 0) {
      return { scaledData: [], joltsMin: 0, joltsMax: 0, indeedMin: 0, indeedMax: 0 }
    }

    // JOLTS・Indeedの最小値・最大値を取得
    const joltsValues = filteredData.map(d => d.jolts).filter((v): v is number => v !== null)
    const indeedValues = filteredData.map(d => d.indeedShifted).filter((v): v is number => v !== null)

    if (joltsValues.length === 0) {
      return { scaledData: filteredData.map(d => ({ ...d, indeedScaled: null })), joltsMin: 0, joltsMax: 0, indeedMin: 0, indeedMax: 0 }
    }

    const jMin = Math.min(...joltsValues)
    const jMax = Math.max(...joltsValues)
    const iMin = indeedValues.length > 0 ? Math.min(...indeedValues) : 0
    const iMax = indeedValues.length > 0 ? Math.max(...indeedValues) : 0

    // IndeedをJOLTSのスケールに変換
    const joltsRange = jMax - jMin
    const indeedRange = iMax - iMin

    const scaled = filteredData.map(d => ({
      ...d,
      indeedScaled: d.indeedShifted !== null && indeedRange > 0
        ? jMin + (d.indeedShifted - iMin) * joltsRange / indeedRange
        : null,
    }))

    return {
      scaledData: scaled,
      joltsMin: jMin,
      joltsMax: jMax,
      indeedMin: iMin,
      indeedMax: iMax
    }
  }, [filteredData])

  // テーブル用データ（共通フックを使用）- JOLTSデータのみを対象に計算
  const joltsOnlyData = useMemo(() => {
    return fullChartData.filter(item => item.jolts !== null)
  }, [fullChartData])

  const changeTableData = useMonthlyTableData(
    joltsOnlyData,
    (item) => item.jolts_change,
    10
  )

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="JOLTS求人 / Indeed求人件数指数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="JOLTS求人 / Indeed求人件数指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release
  const seriesConfig = data.series_config || {}

  // 色を取得（サービス設定 > デフォルト）
  const getColor = (key: string): string => {
    return seriesConfig[key]?.color || DEFAULT_COLORS[key as keyof typeof DEFAULT_COLORS] || '#1890ff'
  }

  // 最新のJOLTS前月増減幅（JOLTSデータのみを対象）
  const latestChange = useMemo(() => {
    const joltsData = fullChartData.filter(d => d.jolts !== null)
    return joltsData.length >= 2 ? joltsData[joltsData.length - 1] : null
  }, [fullChartData])

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (viewMode === 'value') {
      return latest ? [
        { label: SERIES_NAMES.jolts, value: latest.jolts, color: getColor('jolts'), format: 'number' as const, unit: 'k', decimals: 0 },
        { label: SERIES_NAMES.indeed, value: latest.indeed, color: getColor('indeed'), format: 'number' as const, unit: '', decimals: 1 },
      ] : []
    } else {
      // JOLTS前月増減幅モード
      if (!latestChange) return []
      const jChange = latestChange.jolts_change
      return [
        {
          label: `${SERIES_NAMES.jolts}（増減）`,
          value: jChange !== null ? `${jChange >= 0 ? '+' : ''}${jChange.toLocaleString()}k` : 'N/A',
          color: jChange !== null && jChange >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative,
        },
      ]
    }
  }


  return (
    <div id="jolts-indeed">
      <ChartContainer
        title="JOLTS求人 / Indeed求人件数"
        showPeriodSelector={false}
        dataSource="FRED / BLS / Indeed"
        sourceUrl="https://www.bls.gov/jlt/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latestChange?.date || latest?.date}
          nextRelease={nextRelease}
        />

        {/* タブ切替 */}
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
                  {/* ビューモード切り替え */}
                  <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />

                  {/* 現数値グラフ */}
                  {viewMode === 'value' && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                        <AntTooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open('/compare?s=jolts_openings', '_blank')}
                          >
                            データ比較
                          </Button>
                        </AntTooltip>
                      </div>
                      {/* 単一Y軸で両データを表示（IndeedはJOLTSスケールに変換済み） */}
                      <ResponsiveContainer width="100%" height={450}>
                        <ComposedChart data={scaledData} margin={CHART_MARGIN}>
                          <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                          <XAxis
                            dataKey="date"
                            tickFormatter={formatDateLabel}
                            tick={AXIS_STYLE.tick}
                            interval={AXIS_STYLE.interval}
                          />
                          {/* 左Y軸: JOLTS求人件数（千人単位） */}
                          <YAxis
                            yAxisId="left"
                            domain={[joltsMin - 500, joltsMax + 500]}
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v) => `${v.toLocaleString()}`}
                            label={{
                              value: 'JOLTS求人件数（k）',
                              angle: -90,
                              position: 'insideLeft',
                              dy: 50,
                              style: { fontSize: 11, fill: getColor('jolts') }
                            }}
                          />
                          {/* 右Y軸: Indeed求人件数指数（JOLTSスケールに合わせて表示） */}
                          <YAxis
                            yAxisId="right"
                            orientation="right"
                            domain={[joltsMin - 500, joltsMax + 500]}
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v) => {
                              // JOLTSスケールからIndeed指数に逆変換して表示
                              const joltsRange = joltsMax - joltsMin
                              const indeedRange = indeedMax - indeedMin
                              if (joltsRange === 0) return '0'
                              const indeedValue = indeedMin + (v - joltsMin) * indeedRange / joltsRange
                              return indeedValue.toFixed(0)
                            }}
                            label={{
                              value: 'Indeed指数（2020/2=100）',
                              angle: 90,
                              position: 'insideRight',
                              dy: 70,
                              style: { fontSize: 11, fill: getColor('indeed') }
                            }}
                          />
                          <Tooltip content={<ValueTooltip />} />
                          <Legend
                            onClick={(e) => handleLegendClick(e.dataKey as string)}
                            wrapperStyle={{ cursor: 'pointer' }}
                          />

                          {/* JOLTS求人件数（左軸） */}
                          <Line
                            yAxisId="left"
                            type="monotone"
                            dataKey="jolts"
                            stroke={getColor('jolts')}
                            strokeWidth={2}
                            dot={false}
                            name={SERIES_NAMES.jolts}
                            hide={isHidden('jolts')}
                            isAnimationActive={false}
                            connectNulls={true}
                          />

                          {/* Indeed求人件数指数（JOLTSスケールに変換したindeedScaledを使用） */}
                          <Line
                            yAxisId="left"
                            type="monotone"
                            dataKey="indeedScaled"
                            stroke={getColor('indeed')}
                            strokeWidth={2}
                            dot={false}
                            name={SERIES_NAMES.indeed}
                            hide={isHidden('indeed')}
                            isAnimationActive={false}
                            connectNulls={true}
                          />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </>
                  )}

                  {/* JOLTS前月増減幅グラフ */}
                  {viewMode === 'jolts_change_chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <ResponsiveContainer width="100%" height={450}>
                        <ComposedChart data={joltsChangeData} margin={CHART_MARGIN}>
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
                            domain={['dataMin - 100', 'dataMax + 100']}
                            label={{
                              angle: -90,
                              position: 'insideLeft',
                              dy: 30,
                              style: { fontSize: 11, fill: '#666' }
                            }}
                          />
                          <Tooltip content={<ChangeTooltip unit="k" formatValue={(v) => v.toLocaleString()} />} />
                          <Legend />
                          <ReferenceLine y={0} stroke="#000" strokeWidth={1} />

                          {/* JOLTS求人件数 */}
                          <Bar
                            dataKey="jolts_change"
                            fill={getColor('jolts')}
                            name={`${SERIES_NAMES.jolts}（増減）`}
                          />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </>
                  )}

                  {/* JOLTS前月増減幅テーブル */}
                  {viewMode === 'jolts_change_table' && (
                    <MonthlyTable
                      data={changeTableData}
                      formatValue={(value) => {
                        if (value === null) return '-'
                        return `${value >= 0 ? '+' : ''}${value.toLocaleString()}`
                      }}
                      getCellBgColor={getChangeCellColor200k}
                      legendItems={CHANGE_LEGEND_200K}
                      helperText="※ 直近10年間のJOLTS求人件数 前月増減幅データ（単位: 千人）"
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="jolts_openings" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
