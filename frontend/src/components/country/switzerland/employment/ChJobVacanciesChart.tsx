/**
 * スイス求人情報 チャートコンポーネント
 *
 * arbeit.swissから求人件数データを取得し、表示
 *
 * データ:
 * - Job Vacancies（求人件数）
 *
 * データソース:
 * - arbeit.swiss (SECO)
 *
 * 発表スケジュール:
 * - 毎月（失業率と同タイミング、FMPカレンダーから取得）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { CHJobVacanciesData } from '../../../../hooks/useDashboardData'

interface ChJobVacanciesChartProps {
  data: CHJobVacanciesData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  vacancies: '#52c41a', // 緑（求人なのでポジティブな色）
}

export default function ChJobVacanciesChart({ data }: ChJobVacanciesChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 'default',
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
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
    return <LoadingChart title="求人情報" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="求人情報" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-job-vacancies-chart">
      <ChartContainer
        title="求人情報"
        showPeriodSelector={false}
        dataSource="arbeit.swiss (SECO)"
        sourceUrl="https://www.arbeit.swiss/secoalv/de/home/menue/institutionen-medien/statistiken.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="求人件数"
          value={latestValue?.value}
          date={latestValue?.date}
          format="number"
          decimals={0}
          unit=" 件"
          valueColor={COLORS.vacancies}
          nextRelease={data.next_release}
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
                  {/* コントロールバー */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く（スイス求人情報）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ch_job_vacancies', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 期間選択 */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.vacancies, name: '求人件数' },
                    ]}
                    yAxisFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                    tooltipValueFormatter={(v) => `${v.toLocaleString()} 件`}
                    yDomain={['dataMin * 0.9', 'dataMax * 1.1']}
                    showZeroLine={false}
                  />
                </>
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
