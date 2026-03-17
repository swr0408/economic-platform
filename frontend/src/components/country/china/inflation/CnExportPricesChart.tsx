/**
 * 中国 輸出物価指数（Export Price Index）チャートコンポーネント
 *
 * 2モード: 原数値（index） / 前月比（MoM）
 * 原数値: 折れ線グラフ（前年同月=100）
 * 前月比: 棒グラフ / ヒートマップ切替
 *
 * データソース: GACC（海関総署）
 *
 * FMPマッピング: cn_trade_balance → "Exports" etc.
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMultiValueMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../../usa/common/MonthlyTable'

// =============================================================================
// 型定義・定数
// =============================================================================

interface CnExportPricesData {
  data: Array<{ date: string; index: number | null; yoy: number | null; mom: number | null }>
  latest?: { date: string; index: number | null; yoy: number | null; mom: number | null }
  next_release?: string | null
}

interface Props {
  data: CnExportPricesData | null
}

interface ChartDataPoint {
  date: string
  index: number | null
  yoy: number | null
  mom: number | null
}

type ViewMode = 'raw' | 'mom'
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'raw', label: '原数値' },
  { mode: 'mom', label: '前月比' },
]

type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

type DataType = 'total'
const DATA_TYPE_OPTIONS: { type: DataType; label: string }[] = [
  { type: 'total', label: '総合' },
]

const COLOR_PRIMARY = '#1890ff'

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnExportPricesChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<DataType>('total')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    raw: 10,
    mom: 3,
  })

  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data?.data) return []
    return data.data.map(d => ({
      date: d.date,
      index: d.index,
      yoy: d.yoy,
      mom: d.mom,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // ヒートマップ用データ
  const momTableData = useMultiValueMonthlyTableData(
    sortedData,
    {
      total: (item: ChartDataPoint) => item.mom,
    },
    10
  )

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="輸出物価指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="輸出物価指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  // 最新値表示の値とラベル
  const latestDisplayValue = viewMode === 'raw'
    ? (latest?.index ?? null)
    : (latest?.mom ?? null)
  const latestLabel = viewMode === 'raw'
    ? '輸出物価指数'
    : '輸出物価（MoM）'
  const latestUnit = viewMode === 'raw' ? undefined : undefined

  return (
    <div id="export-prices">
      <ChartContainer
        title="輸出物価指数"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="GACC"
        sourceUrl="http://english.customs.gov.cn/statics/report/trade.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={latestLabel}
          value={latestDisplayValue}
          date={latest?.date}
          unit={latestUnit}
          decimals={viewMode === 'raw' ? 1 : 1}
          valueColor={COLOR_PRIMARY}
          dateFormatter={formatDateFull}
          nextRelease={data.next_release ? { date: data.next_release } : null}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          size="small"
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* ViewMode + 比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_export_prices', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前月比: チャート/ヒートマップ切替 */}
                  {viewMode === 'mom' && (
                    <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                  )}

                  {/* 原数値グラフ（折れ線グラフ + 100基準線） */}
                  {viewMode === 'raw' && (
                    <>
                      <PeriodSelector
                        onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
                        selectedPeriod={currentPeriod}
                      />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'index', color: COLOR_PRIMARY, name: '輸出物価指数' },
                        ]}
                        yAxisFormatter={(v) => `${v.toFixed(0)}`}
                        yDomain={['dataMin - 3', 'dataMax + 3']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateFull}
                        tooltipValueFormatter={(v) => `${v.toFixed(1)}`}
                        showZeroLine={false}
                        showLegend={false}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {viewMode === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                      decimals={1}
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {viewMode === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector
                        onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
                        selectedPeriod={currentPeriod}
                      />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'mom', color: COLOR_PRIMARY, name: '輸出物価（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v.toFixed(1)}`}
                        yDomain={['dataMin - 2', 'dataMax + 2']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateFull}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}`}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="cn_trade_balance" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
