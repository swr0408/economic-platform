/**
 * ECB Consumer Expectations Survey（CES）賃金期待チャートコンポーネント
 *
 * 家計所得12ヶ月先見通し（% change、加重平均）
 *
 * データソース:
 * - ECB Data Portal (CES dataset)
 *
 * 発表スケジュール:
 * - 月次（毎月下旬）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { usePeriodFiltering, type PeriodType } from '../../usa/common/useChartData'
import { CHART_COLORS } from '../../usa/common/chartConstants'

import type { ECBCesWageExpectationsData } from '../../../../hooks/useDashboardData'

interface EcbCesWageExpectationsChartProps {
  data: ECBCesWageExpectationsData | null
}

const COLORS = {
  wage: CHART_COLORS.primary,
}

export default function EcbCesWageExpectationsChart({ data }: EcbCesWageExpectationsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('all')

  const chartData = useMemo(() => {
    if (!data?.data) return []

    return data.data
      .map((item) => ({
        date: item.date,
        value: item.value,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2022,
  })

  // Y軸ドメインを計算
  const yDomain = useMemo((): [number, number] => {
    if (filteredData.length === 0) return [0, 2]
    const values = filteredData.map(d => d.value).filter((v): v is number => v != null)
    const min = Math.min(...values)
    const max = Math.max(...values)
    return [Math.floor((min - 0.2) * 10) / 10, Math.ceil((max + 0.2) * 10) / 10]
  }, [filteredData])

  const hasData = chartData.length > 0
  const latest = data?.latest ?? null

  if (data === null) {
    return <LoadingChart title="CES 賃金期待" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="CES 賃金期待" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-ces-wage-expectations-chart">
      <ChartContainer
        title="CES 賃金期待（家計所得12ヶ月先見通し）"
        showPeriodSelector={false}
        dataSource="ECB"
        sourceUrl="https://www.ecb.europa.eu/stats/ecb_surveys/consumer_exp_survey/html/index.en.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={COLORS.wage}
          date={latest?.date}
          nextRelease={data?.next_release ? { date: data.next_release.date, time_jst: data.next_release.time_jst } : undefined}
          format="percent"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ecb_ces_wage_expectations', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLORS.wage, name: '賃金期待（加重平均）' },
          ]}
          yAxisFormatter={(v) => `${Number(v).toFixed(1)}%`}
          tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
          yDomain={yDomain}
          showZeroLine={true}
        />
      </ChartContainer>
    </div>
  )
}
