/**
 * 中古車価格 チャート（FRED CPI Used Cars + Manheim UVVI YoY）
 *
 * 2系列の前年比を折れ線グラフで表示:
 * - FRED: CPI Used Cars and Trucks YoY (CUSR0000SETA02) — 公式CPI
 * - Manheim: Used Vehicle Value Index YoY — 卸売段階の先行指標
 *
 * データソース:
 * - FRED: https://fred.stlouisfed.org/series/CUSR0000SETA02
 * - Manheim: https://www.coxautoinc.com/insights/?insight_series=manheim-used-vehicle-index
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { UsedCarPricesData } from '../../../../hooks/useDashboardData'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../common/ChartComponents'

interface UsedCarPricesChartProps {
  data: UsedCarPricesData | null
}

const COLOR_FRED = '#3b82f6'      // FRED公式CPI（青）
const COLOR_MANHEIM = '#f97316'   // Manheim卸売先行指標（オレンジ）

export default function UsedCarPricesChart({ data }: UsedCarPricesChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const sortedData = useSortedData(data?.data)

  const chartData = useMemo(
    () =>
      sortedData.map((item) => ({
        date: item.date,
        fred_yoy: item.fred_yoy,
        manheim_yoy: item.manheim_yoy,
      })),
    [sortedData],
  )

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2015,
  })

  // 各系列は別タイミング更新のため、それぞれの最新値を取得（早期returnより前に配置）
  const latestFred = useMemo(() => {
    for (let i = sortedData.length - 1; i >= 0; i--) {
      if (sortedData[i].fred_yoy != null) return sortedData[i]
    }
    return null
  }, [sortedData])

  const latestManheim = useMemo(() => {
    for (let i = sortedData.length - 1; i >= 0; i--) {
      if (sortedData[i].manheim_yoy != null) return sortedData[i]
    }
    return null
  }, [sortedData])

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="中古車価格（CPI 中古車 / Manheim 中古車 前年比）" />
  }

  if (!hasData) {
    return (
      <ChartContainer
        title="中古車価格（CPI 中古車 / Manheim 中古車 前年比）"
        showPeriodSelector={false}
        showDataSource={false}
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="used-car-prices">
      <ChartContainer
        title="中古車価格（CPI 中古車 / Manheim 中古車 前年比）"
        showPeriodSelector={false}
        dataSource="FRED / Manheim (Cox Automotive)"
        sourceUrl="https://www.coxautoinc.com/insights/?insight_series=manheim-used-vehicle-index"
        handbookId="used-car-prices"
      >
        <LatestValueBox
          items={[
            {
              label: `CPI 中古車 (${latestFred?.date ?? '-'})`,
              value: latestFred?.fred_yoy,
              color: COLOR_FRED,
              format: 'percent',
            },
            {
              label: `Manheim 中古車 (${latestManheim?.date ?? '-'})`,
              value: latestManheim?.manheim_yoy,
              color: COLOR_MANHEIM,
              format: 'percent',
            },
          ]}
          nextRelease={data.next_release}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector
            onPeriodChange={setSelectedPeriod}
            selectedPeriod={selectedPeriod}
          />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=us_cpi_used_cars_yoy&s=us_manheim_used_vehicle_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'fred_yoy',
              color: COLOR_FRED,
              name: 'CPI 中古車 YoY',
              hide: hiddenSeries.has('fred_yoy'),
            },
            {
              dataKey: 'manheim_yoy',
              color: COLOR_MANHEIM,
              name: 'Manheim 中古車 YoY',
              hide: hiddenSeries.has('manheim_yoy'),
            },
          ]}
          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
          tooltipValueFormatter={(v) => (v != null ? `${v.toFixed(2)}%` : 'N/A')}
          showZeroLine={true}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
