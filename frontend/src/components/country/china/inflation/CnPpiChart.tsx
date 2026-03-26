/**
 * 中国 PPI（Producer Price Index）チャートコンポーネント
 *
 * 2系列: PPI前年比（YoY）/ PPI前月比（MoM）
 * 前年比: 折れ線グラフ
 * 前月比: 棒グラフ / ヒートマップ切替
 *
 * データソース: NBS
 *
 * FMPマッピング: cn_ppi → "Producer Price Index YoY"
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

import type { CnPpiData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnPpiData | null
}

interface ChartDataPoint {
  date: string
  yoy: number | null
  mom: number | null
}

type DataKind = 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// ヒートマップ用データタイプ（PPIは総合のみ）
type PPIDataType = 'total'
const PPI_DATA_TYPE_OPTIONS: { type: PPIDataType; label: string }[] = [
  { type: 'total', label: '総合' },
]

const COLOR_PRIMARY = '#E07C24' // オレンジ系

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

export default function CnPpiChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<PPIDataType>('total')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data?.data) return []
    return data.data.map(d => ({
      date: d.date,
      yoy: d.yoy,
      mom: d.mom,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
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
    return <LoadingChart title="PPI（生産者物価指数）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="PPI（生産者物価指数）" showPeriodSelector={false} showDataSource={false} handbookId="cn-ppi">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="ppi">
      <ChartContainer
        title="PPI（生産者物価指数）"
        showPeriodSelector={false}
        handbookId="cn-ppi"
        showDataSource={true}
        dataSource="NBS"
        sourceUrl="https://www.stats.gov.cn/english/PressRelease/index.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={dataKind === 'yoy' ? 'PPI（YoY）' : 'PPI（MoM）'}
          value={dataKind === 'yoy' ? (latest?.yoy ?? null) : (latest?.mom ?? null)}
          date={latest?.date}
          unit="%"
          decimals={1}
          valueColor={COLOR_PRIMARY}
          dateFormatter={formatDateFull}
          nextRelease={data.next_release ?? null}
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
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_ppi', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 前月比: チャート/ヒートマップ切替 */}
                  {dataKind === 'mom' && (
                    <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                  )}

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector
                        onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
                        selectedPeriod={currentPeriod}
                      />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: COLOR_PRIMARY, name: 'PPI（前年比）' },
                        ]}
                        yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateFull}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        showZeroLine={true}
                        showLegend={false}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={PPI_DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                      decimals={1}
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector
                        onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
                        selectedPeriod={currentPeriod}
                      />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'mom', color: COLOR_PRIMARY, name: 'PPI（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateFull}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
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
                <MarketImpactTab indicatorId="cn_ppi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
