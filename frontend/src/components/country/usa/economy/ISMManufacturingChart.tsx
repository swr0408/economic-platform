import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { ISMManufacturingData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { usePeriodFiltering, useViewModePeriodManagement } from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox, ViewModeButtonGroup, StandardBarChart } from '../common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

type ViewMode = 'raw' | '3m_change'
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'raw', label: '水準' },
  { mode: '3m_change', label: '3か月方向' },
]

const CHART_COLOR = '#1890ff'
const BAR_COLOR = '#f97316'

interface ISMManufacturingChartProps {
  data: ISMManufacturingData | null
}

export default function ISMManufacturingChart({ data }: ISMManufacturingChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, { raw: 10, '3m_change': 10 })

  // データを日付昇順にソートしてDataPoint型に変換
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        value: item.value,
      }))
  }, [data])

  // 3か月方向データの算出
  const change3mData = useMemo(() => {
    if (chartData.length < 4) return []
    return chartData.slice(3).map((item, i) => ({
      date: item.date,
      change_3m: Math.round((item.value - chartData[i].value) * 10) / 10,
    }))
  }, [chartData])

  // 期間フィルタリング
  const filteredRawData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })
  const filteredChange3mData = usePeriodFiltering(change3mData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="ISM製造業景況指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ISM製造業景況指数" showPeriodSelector={false} showDataSource={false} handbookId="ism-manufacturing">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const formatValue = (value: number) => value.toFixed(1)

  const compareId = viewMode === '3m_change' ? 'ism_manufacturing_3m_change' : 'ism_manufacturing'

  return (
    <div id="ism-manufacturing-chart">
      <ChartContainer
        title="ISM製造業景況指数"
        showPeriodSelector={false}
        dataSource="ISM"
        handbookId="ism-manufacturing"
        sourceUrl="https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={data.latest?.value}
          valueColor={CHART_COLOR}
          date={data.latest?.date}
          nextRelease={data.next_release}
          format="number"
          decimals={1}
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
                  {/* ViewMode + 比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={(m) => setViewMode(m as ViewMode)} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=${compareId}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* PeriodSelector */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* 水準チャート */}
                  {viewMode === 'raw' && (
                    <ZoomableChart
                      data={filteredRawData}
                      dataKey="value"
                      color={CHART_COLOR}
                      name="ISM製造業景況指数"
                      height={450}
                      tickFormatter={formatValue}
                      tooltipFormatter={formatValue}
                      enableDynamicTicks={true}
                      showZeroLine={false}
                      showFiftyLine={true}
                      fiftyLineValue={50}
                      connectNulls={true}
                      hideLegend={true}
                    />
                  )}

                  {/* 3か月方向バーチャート */}
                  {viewMode === '3m_change' && (
                    <StandardBarChart
                      data={filteredChange3mData}
                      bars={[{ dataKey: 'change_3m', color: BAR_COLOR, name: 'ISM製造業（3か月方向）' }]}
                      yAxisFormatter={(v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}`}
                      tooltipValueFormatter={(v) => `${v > 0 ? '+' : ''}${v.toFixed(1)} pt`}
                      yDomain={['dataMin - 2', 'dataMax + 2']}
                      showZeroLine={true}
                      showLegend={false}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ism_manufacturing" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
