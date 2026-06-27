/**
 * NZ CPI項目別チャートコンポーネント
 *
 * データ:
 * - Food（食料）YoY%
 * - Actual rentals for housing（家賃）YoY%
 * - Purchase of housing（住宅購入）YoY%
 * - Electricity（電気）YoY%
 * - Gas（ガス）YoY%
 *
 * データソース:
 * - Stats NZ Consumers Price Index
 * - https://www.stats.govt.nz/indicators/consumers-price-index-cpi/
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzCpiItemData } from '../../../../hooks/useDashboardData'

interface NzCpiItemChartProps {
  data: NzCpiItemData | null
}

interface ChartDataPoint {
  date: string
  food_yoy: number | null
  rentals_yoy: number | null
  purchase_housing_yoy: number | null
  electricity_yoy: number | null
  gas_yoy: number | null
}

const COLORS = {
  food: '#f59e0b',
  rentals: '#2563eb',
  purchase_housing: '#8b5cf6',
  electricity: '#dc2626',
  gas: '#16a34a',
}

const formatQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}/Q${quarter}`
}

const formatQuarterLabelJP = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}年 Q${quarter}`
}

export default function NzCpiItemChart({ data }: NzCpiItemChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((item) =>
        item.food_yoy !== null || item.rentals_yoy !== null ||
        item.purchase_housing_yoy !== null || item.electricity_yoy !== null ||
        item.gas_yoy !== null
      )
      .map((item) => ({
        date: item.date,
        food_yoy: item.food_yoy,
        rentals_yoy: item.rentals_yoy,
        purchase_housing_yoy: item.purchase_housing_yoy,
        electricity_yoy: item.electricity_yoy,
        gas_yoy: item.gas_yoy,
      }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="CPI 項目別" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CPI 項目別" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="cpi-item">
      <ChartContainer
        title="CPI 項目別（前年比）"
        showPeriodSelector={false}
        dataSource="Stats NZ"
        sourceUrl="https://www.stats.govt.nz/indicators/consumers-price-index-cpi/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '食料',
              value: latest?.food_yoy,
              color: COLORS.food,
              format: 'percent',
            },
            {
              label: '家賃',
              value: latest?.rentals_yoy,
              color: COLORS.rentals,
              format: 'percent',
            },
            {
              label: '電気',
              value: latest?.electricity_yoy,
              color: COLORS.electricity,
              format: 'percent',
            },
            {
              label: 'ガス',
              value: latest?.gas_yoy,
              color: COLORS.gas,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatQuarterLabelJP}
          nextRelease={data?.next_release ? { date: data.next_release.date } : undefined}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_cpi_item_food&s=nz_cpi_item_rentals&s=nz_cpi_item_electricity&s=nz_cpi_item_gas&s=nz_cpi_item_housing', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'food_yoy', color: COLORS.food, name: '食料', hide: hiddenSeries.has('food_yoy') },
                      { dataKey: 'rentals_yoy', color: COLORS.rentals, name: '家賃', hide: hiddenSeries.has('rentals_yoy'), yAxisId: 'right' },
                      { dataKey: 'purchase_housing_yoy', color: COLORS.purchase_housing, name: '住宅購入', hide: hiddenSeries.has('purchase_housing_yoy') },
                      { dataKey: 'electricity_yoy', color: COLORS.electricity, name: '電気', hide: hiddenSeries.has('electricity_yoy') },
                      { dataKey: 'gas_yoy', color: COLORS.gas, name: 'ガス', hide: hiddenSeries.has('gas_yoy') },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                    yDomain={['dataMin - 2', 'dataMax + 2']}
                    showZeroLine={true}
                    xAxisFormatter={formatQuarterLabel}
                    tooltipLabelFormatter={formatQuarterLabelJP}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="nz_cpi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
