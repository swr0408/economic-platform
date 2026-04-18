/**
 * カナダCPI サービス/家賃（粘着性CPI）チャートコンポーネント
 *
 * BoCが重視するサービス/家賃セクターのインフレ動向を表示
 * 「総合」「コア」「サービス」「住居」「家賃」のYoYを一覧
 *
 * データソース:
 * - Statistics Canada WDS API (Table 18-10-0004-01)
 *
 * 発表スケジュール:
 * - 毎月中旬
 * - 発表時刻: 08:30 ET
 */
import { useMemo, useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

import type { CaCpiServiceRentData } from '../../../../hooks/useDashboardData'

interface CaCpiServiceRentChartProps {
  data: CaCpiServiceRentData | null
}

const COLORS = {
  all_items: '#999999',
  ex_food_energy: CHART_COLORS.primary,
  services: '#DC143C',
  shelter: '#faad14',
  rent: '#52c41a',
}

export default function CaCpiServiceRentChart({ data }: CaCpiServiceRentChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        all_items: item.all_items ?? null,
        ex_food_energy: item.ex_food_energy ?? null,
        services: item.services ?? null,
        shelter: item.shelter ?? null,
        rent: item.rent ?? null,
      }))
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0
  const latestValue = data?.latest

  if (data === null) {
    return <LoadingChart title="CPI サービス/家賃（粘着性CPI）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CPI サービス/家賃（粘着性CPI）" showPeriodSelector={false} showDataSource={false} handbookId="cpi-service-rent">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const lines = [
    { dataKey: 'all_items', color: COLORS.all_items, name: 'CPI 総合', hide: hiddenSeries.has('all_items') },
    { dataKey: 'ex_food_energy', color: COLORS.ex_food_energy, name: 'CPI コア（除く食品・エネルギー）', hide: hiddenSeries.has('ex_food_energy') },
    { dataKey: 'services', color: COLORS.services, name: 'CPI サービス', hide: hiddenSeries.has('services') },
    { dataKey: 'shelter', color: COLORS.shelter, name: 'CPI 住居', hide: hiddenSeries.has('shelter') },
    { dataKey: 'rent', color: COLORS.rent, name: 'CPI 家賃', hide: hiddenSeries.has('rent') },
  ]

  return (
    <div id="ca-cpi-service-rent-chart">
      <ChartContainer
        title="CPI サービス/家賃（粘着性CPI）"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401"
        handbookId="cpi-service-rent"
      >
        <SimpleLatestValueBox
          label="CPI サービス（YoY）"
          value={latestValue?.services}
          date={latestValue?.date}
          format="percent"
          decimals={2}
          valueColor={COLORS.services}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ca_cpi_services_yoy&s=ca_cpi_rent_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <StandardLineChart
          data={filteredData}
          lines={lines}
          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
          tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          showZeroLine={true}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
