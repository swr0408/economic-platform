/**
 * Eurostat求人欠員率チャートコンポーネント
 *
 * Eurostat APIから求人欠員率データを取得し、表示
 *
 * データ:
 * - Job Vacancy Rate (求人欠員率)
 *
 * データソース:
 * - Eurostat - Job Vacancy Statistics (jvs_q_nace2)
 *
 * 発表スケジュール:
 * - 3月・6月・9月・12月（不定期）
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

import type { EurostatJobVacancyData } from '../../../../hooks/useDashboardData'

interface EurostatJobVacancyChartProps {
  data: EurostatJobVacancyData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  jobVacancy: '#52c41a',
}

/**
 * 四半期形式の日付（2025-Q2）をソート可能な形式に変換
 */
function parseQuarterDate(dateStr: string): Date {
  // YYYY-QN 形式をパース
  const match = dateStr.match(/^(\d{4})-Q([1-4])$/)
  if (match) {
    const year = parseInt(match[1], 10)
    const quarter = parseInt(match[2], 10)
    // 四半期の最初の月（Q1=0, Q2=3, Q3=6, Q4=9）
    const month = (quarter - 1) * 3
    return new Date(year, month, 1)
  }
  // 通常の日付形式
  return new Date(dateStr)
}

/**
 * 四半期日付を日本語表記に変換
 */
function formatQuarterDateJP(dateStr: string): string {
  const match = dateStr.match(/^(\d{4})-Q([1-4])$/)
  if (match) {
    const year = match[1]
    const quarter = parseInt(match[2], 10)
    const quarterNames = ['1-3月期', '4-6月期', '7-9月期', '10-12月期']
    return `${year}年${quarterNames[quarter - 1]}`
  }
  return dateStr
}

/**
 * 四半期データを期間でフィルタリング
 */
function filterQuarterlyData<T extends { date: string }>(
  data: T[],
  selectedPeriod: number | 'all' | 'default'
): T[] {
  if (data.length === 0) return []
  if (selectedPeriod === 'all') return data

  const now = new Date()
  let cutoffDate: Date

  if (selectedPeriod === 'default') {
    // デフォルトは2020年以降
    cutoffDate = new Date(2020, 0, 1)
  } else {
    cutoffDate = new Date(now.getFullYear() - selectedPeriod, now.getMonth(), 1)
  }

  return data.filter((item) => {
    const itemDate = parseQuarterDate(item.date)
    return itemDate >= cutoffDate
  })
}

export default function EurostatJobVacancyChart({ data }: EurostatJobVacancyChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<number | 'all' | 'default'>(20)

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter(item => item.value !== null)
      .map(item => ({
        date: item.date,
        value: item.value,
      }))
      .sort((a, b) =>
        parseQuarterDate(a.date).getTime() - parseQuarterDate(b.date).getTime()
      )
  }, [data])

  // 期間フィルタリング（四半期データ用）
  const filteredData = useMemo(() =>
    filterQuarterlyData(chartData, currentPeriod),
    [chartData, currentPeriod]
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!data?.latest) return null
    return data.latest
  }, [data])

  // 次回発表日のフォーマット
  const formatNextRelease = () => {
    if (!data?.next_release) return null
    const nr = data.next_release
    if (nr.label) {
      return nr.label
    }
    if (nr.date) {
      return nr.date
    }
    return null
  }

  if (data === null) {
    return <LoadingChart title="求人欠員率（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="求人欠員率（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="eurostat-job-vacancy-chart">
      <ChartContainer
        title="求人率（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="Eurostat"
        sourceUrl="https://ec.europa.eu/eurostat/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=BIWPEEzW&text=job+vacancy"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={COLORS.jobVacancy}
          date={latest?.date}
          nextRelease={formatNextRelease() ? { date: formatNextRelease()! } : undefined}
          format="percent"
          dateFormatter={formatQuarterDateJP}
        />

        {/* 期間セレクター */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8, marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=eurostat_job_vacancy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLORS.jobVacancy, name: '求人欠員率' },
          ]}
          xAxisFormatter={(date) => date.replace('-', ' ')}
          tooltipLabelFormatter={formatQuarterDateJP}
          yAxisFormatter={(v) => `${Number(v).toFixed(1)}%`}
          tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
          yDomain={['dataMin - 0.2', 'dataMax + 0.2']}
        />
      </ChartContainer>
    </div>
  )
}
