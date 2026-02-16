/**
 * カナダ求人率 チャートコンポーネント
 *
 * Statistics Canada から求人率データを取得し、表示
 *
 * データ:
 * - Job Vacancy Rate（求人率）% — 季節調整済
 *
 * データソース:
 * - Statistics Canada Table 14-10-0432-01
 *
 * 発表スケジュール:
 * - 毎月発表
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { CaJobVacancyRateData } from '../../../../hooks/useDashboardData'

interface CaJobVacancyRateChartProps {
  data: CaJobVacancyRateData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

const COLORS = {
  vacancy: '#1890ff',
}

export default function CaJobVacancyRateChart({ data }: CaJobVacancyRateChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>('default')

  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  const chartData = useSortedData(rawChartData)

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  const latestValue = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].value !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="カナダ求人率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="カナダ求人率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ca-job-vacancy-rate-chart">
      <ChartContainer
        title="求人率"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410043201"
      >
        <SimpleLatestValueBox
          label="求人率"
          value={latestValue?.value}
          date={latestValue?.date}
          format="percent"
          decimals={1}
          valueColor={COLORS.vacancy}
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
              onClick={() => window.open('/compare?s=ca_job_vacancy_rate', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLORS.vacancy, name: '求人率' },
          ]}
          yAxisFormatter={(v) => `${v}%`}
          tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
