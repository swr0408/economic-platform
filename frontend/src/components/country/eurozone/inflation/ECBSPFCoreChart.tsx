/**
 * ECB SPF Core コアインフレ期待チャートコンポーネント
 *
 * ECB Data APIからSurvey of Professional Forecasters (SPF)コアインフレデータを取得し、表示
 *
 * データ:
 * - コアHICP 1年先予測
 * - コアHICP 2年先予測
 * - コアHICP 5年先予測（長期）
 *
 * データソース:
 * - European Central Bank (ECB)
 *
 * 発表スケジュール:
 * - 発表: 1月・4月・7月・10月（四半期ごと）
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
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { ECBSPFCoreData } from '../../../../hooks/useDashboardData'

interface ECBSPFCoreChartProps {
  data: ECBSPFCoreData | null
}

interface ChartDataPoint {
  date: string
  core_1y: number | null
  core_2y: number | null
  core_5y: number | null
  [key: string]: unknown
}

// 色設定（MacroMicroに合わせた配色）
const COLORS = {
  core_1y: '#5DADE2',  // 水色（1年先）
  core_2y: '#E74C3C',  // 赤色（2年先）
  core_5y: '#F4D03F',  // 黄色（5年先）
}

// 日付フォーマット（四半期対応）
function formatSPFDate(dateStr: string): string {
  if (dateStr.includes('-Q')) {
    // 四半期形式: 2025-Q1 → 2025Q1
    const [year, quarter] = dateStr.split('-')
    return `${year}${quarter}`
  }
  // 月次形式: 2025-01 → 2025/01
  return dateStr.replace('-', '/')
}

// 四半期日付を月次形式に変換（ソート用）
function normalizeDate(dateStr: string): string {
  if (dateStr.includes('-Q')) {
    const [year, quarter] = dateStr.split('-Q')
    const month = ((parseInt(quarter) - 1) * 3 + 1).toString().padStart(2, '0')
    return `${year}-${month}`
  }
  return dateStr
}

export default function ECBSPFCoreChart({ data }: ECBSPFCoreChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 'default',
  })

  // 3系列のデータをマージ（発表期をX軸に）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data || !data.inflation_expectations) return []

    const core12m = data.inflation_expectations.core_12m || []
    const core24m = data.inflation_expectations.core_24m || []
    const coreLt = data.inflation_expectations.core_lt || []

    // 日付をキーにしたマップを作成
    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      core_1y: null,
      core_2y: null,
      core_5y: null,
    })

    // 12ヶ月先（1年先）データ
    core12m.forEach((point) => {
      const normalizedDate = normalizeDate(point.date)
      if (!dateMap.has(normalizedDate)) {
        dateMap.set(normalizedDate, initPoint(normalizedDate))
      }
      dateMap.get(normalizedDate)!.core_1y = point.value
    })

    // 24ヶ月先（2年先）データ
    core24m.forEach((point) => {
      const normalizedDate = normalizeDate(point.date)
      if (!dateMap.has(normalizedDate)) {
        dateMap.set(normalizedDate, initPoint(normalizedDate))
      }
      dateMap.get(normalizedDate)!.core_2y = point.value
    })

    // 長期（5年先）データ
    coreLt.forEach((point) => {
      const normalizedDate = normalizeDate(point.date)
      if (!dateMap.has(normalizedDate)) {
        dateMap.set(normalizedDate, initPoint(normalizedDate))
      }
      dateMap.get(normalizedDate)!.core_5y = point.value
    })

    return Array.from(dateMap.values())
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 各系列の最新値を取得
  const latest1y = useMemo(() => {
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].core_1y !== null) {
        return { date: chartData[i].date, value: chartData[i].core_1y }
      }
    }
    return null
  }, [chartData])

  const latest2y = useMemo(() => {
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].core_2y !== null) {
        return { date: chartData[i].date, value: chartData[i].core_2y }
      }
    }
    return null
  }, [chartData])

  const latest5y = useMemo(() => {
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].core_5y !== null) {
        return { date: chartData[i].date, value: chartData[i].core_5y }
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="コアインフレ期待（ユーロ圏・SPF）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="コアインフレ期待（ユーロ圏・SPF）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-spf-core-chart">
      <ChartContainer
        title="コアインフレ期待（ユーロ圏・SPF）"
        showPeriodSelector={false}
        dataSource="European Central Bank (ECB)"
        sourceUrl="https://www.ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/html/index.en.html"
      >
        {/* 最新値表示（3系列） */}
        <LatestValueBox
          items={[
            {
              label: '1年先',
              value: latest1y?.value,
              color: COLORS.core_1y,
              format: 'percent',
            },
            {
              label: '2年先',
              value: latest2y?.value,
              color: COLORS.core_2y,
              format: 'percent',
            },
            {
              label: '5年先',
              value: latest5y?.value,
              color: COLORS.core_5y,
              format: 'percent',
            },
          ]}
          date={latest1y?.date ? formatSPFDate(latest1y.date) : undefined}
          nextRelease={data.next_release ? { date: data.next_release } : null}
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
                  {/* データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く（コアインフレ期待）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() =>
                          window.open(
                            '/compare?s=eurozone_spf_core_12m&s=eurozone_spf_core_24m&s=eurozone_spf_core_lt',
                            '_blank'
                          )
                        }
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      {
                        dataKey: 'core_1y',
                        color: COLORS.core_1y,
                        name: '1年先',
                      },
                      {
                        dataKey: 'core_2y',
                        color: COLORS.core_2y,
                        name: '2年先',
                      },
                      {
                        dataKey: 'core_5y',
                        color: COLORS.core_5y,
                        name: '5年先',
                      },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    yDomain={['dataMin - 0.2', 'dataMax + 0.2']}
                    showZeroLine={false}
                    xAxisFormatter={(dateStr: string) => formatSPFDate(dateStr)}
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
