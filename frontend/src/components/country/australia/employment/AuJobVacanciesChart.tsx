/**
 * AU Job Vacancies Chart Component
 * オーストラリア 求人件数チャート
 *
 * データ項目:
 * - value: Job Vacancies (thousands, Seasonally Adjusted)
 *
 * データソース: Australian Bureau of Statistics (ABS)
 */

import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuJobVacanciesData, AuJobVacanciesDataPoint } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  value: number | null
}

interface AuJobVacanciesChartProps {
  data: AuJobVacanciesData | null
}

// カラー設定
const CHART_COLOR = '#E67E22'

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const month = date.getMonth() + 1
  const quarter = Math.ceil(month / 3)
  return `${date.getFullYear()}/Q${quarter}`
}

const formatDateLabelJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  const month = date.getMonth() + 1
  const quarter = Math.ceil(month / 3)
  return `${date.getFullYear()}年 Q${quarter}`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function AuJobVacanciesChart({ data }: AuJobVacanciesChartProps) {
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: AuJobVacanciesDataPoint) => d.value !== null)
      .map((d: AuJobVacanciesDataPoint) => ({
        date: d.date,
        value: d.value,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  const hasData = sortedData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="求人件数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="求人件数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  return (
    <div id="au-job-vacancies-chart">
      <ChartContainer
        title="求人件数"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Australian Bureau of Statistics"
        sourceUrl="https://www.abs.gov.au/statistics/labour/jobs/job-vacancies-australia"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="求人件数"
          value={latest?.value}
          unit="千件"
          date={latest?.date}
          dateFormatter={formatDateLabelJP}
          valueColor={CHART_COLOR}
          nextRelease={data?.next_release ?? undefined}
          format="number"
          decimals={1}
        />

        {/* タブ切替 */}
        <Tabs
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <TimeSeriesView
                  data={sortedData}
                  hiddenSeries={hiddenSeries}
                  handleLegendClick={handleLegendClick}
                />
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="au_job_vacancies" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}

// =============================================================================
// 時系列ビュー
// =============================================================================

function TimeSeriesView({
  data,
  hiddenSeries,
  handleLegendClick,
}: {
  data: ChartDataPoint[]
  hiddenSeries: Set<string>
  handleLegendClick: (dataKey: string) => void
}) {
  const { filteredData, selectedPeriod, setSelectedPeriod } = usePeriodFilteringWithState(data)

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            onClick={() => window.open('/compare?s=au_job_vacancies', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      <StandardLineChart
        data={filteredData}
        lines={[
          { dataKey: 'value', color: CHART_COLOR, name: '求人件数（千件）', hide: hiddenSeries.has('value') },
        ]}
        yAxisFormatter={(v) => `${v}`}
        yDomain={['dataMin - 20', 'dataMax + 20']}
        xAxisFormatter={formatDateLabel}
        tooltipLabelFormatter={formatDateLabelJP}
        tooltipValueFormatter={(v) => `${v.toFixed(1)} 千件`}
        onLegendClick={handleLegendClick}
      />
    </>
  )
}

// PeriodSelector state wrapper
function usePeriodFilteringWithState(data: ChartDataPoint[]) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>('default')
  const filteredData = usePeriodFiltering(data, {
    selectedPeriod,
    defaultStartYear: 2015,
  })
  return { filteredData, selectedPeriod, setSelectedPeriod }
}
