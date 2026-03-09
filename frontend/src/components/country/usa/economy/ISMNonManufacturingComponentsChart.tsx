import { useState, useMemo } from 'react'
import { Tabs } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { ISMNonManufacturingComponentsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, useHiddenSeries, createNumberFormatter, type PeriodType } from '../common/useChartData'
import { NoDataMessage, LatestValueBox, StandardLineChart } from '../common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

interface ISMNonManufacturingComponentsChartProps {
  data: ISMNonManufacturingComponentsData | null
}

// サブインデックスの設定（非製造業用：productionの代わりにbusiness_activity）
const SERIES_CONFIG = {
  new_orders: { name: '新規受注', color: '#1890ff' },
  business_activity: { name: '業況活動', color: '#52c41a' },
  employment: { name: '雇用', color: '#faad14' },
  prices: { name: '価格（仕入価格）', color: '#f5222d' },
  supplier_deliveries: { name: 'サプライヤー配送', color: '#9346ff' },
} as const

type SeriesKey = keyof typeof SERIES_CONFIG

export default function ISMNonManufacturingComponentsChart({ data }: ISMNonManufacturingComponentsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<SeriesKey>()

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        new_orders: item.new_orders,
        business_activity: item.business_activity,
        employment: item.employment,
        prices: item.prices,
        supplier_deliveries: item.supplier_deliveries,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="ISM非製造業サブインデックス" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ISM非製造業サブインデックス" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値表示用アイテムを生成
  const latestItems = data.latest
    ? Object.entries(SERIES_CONFIG).map(([key, config]) => ({
        label: config.name,
        value: data.latest?.[key as keyof typeof data.latest] as number | null,
        format: 'number' as const,
        decimals: 1,
        color: config.color,
      }))
    : []

  // ライン設定を生成
  const lines = Object.entries(SERIES_CONFIG).map(([key, config]) => ({
    dataKey: key,
    color: config.color,
    name: config.name,
    hide: hiddenSeries.has(key as SeriesKey),
  }))

  return (
    <div id="ism-non-manufacturing-components-chart">
      <ChartContainer
        title="ISM非製造業サブインデックス"
        showPeriodSelector={false}
        dataSource="ISM"
        sourceUrl="https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/"
      >
        {/* 最新値表示 */}
        {data.latest && (
          <LatestValueBox
            items={latestItems}
            date={data.latest.date}
          />
        )}

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
                  <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

                  <StandardLineChart
                    data={filteredData}
                    lines={lines}
                    yAxisFormatter={(v) => v.toFixed(0)}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                    tooltipLabelFormatter={formatDateLabel}
                    tooltipFormatter={createNumberFormatter(1)}
                    onLegendClick={handleLegendClick}
                    showFiftyLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ism_non_manufacturing" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
