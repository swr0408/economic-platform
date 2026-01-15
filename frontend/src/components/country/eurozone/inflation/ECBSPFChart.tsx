/**
 * ECB SPF インフレ期待チャートコンポーネント
 *
 * ECB Data APIからSurvey of Professional Forecasters (SPF)データを取得し、表示
 *
 * データ:
 * - HICP 1年先予測
 * - HICP 2年先予測
 * - HICP 5年先予測（長期）
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

import type { ECBSPFData } from '../../../../hooks/useDashboardData'

interface ECBSPFChartProps {
  data: ECBSPFData | null
}

interface ChartDataPoint {
  date: string
  hicp_1y: number | null
  hicp_2y: number | null
  hicp_5y: number | null
  [key: string]: unknown
}

// 色設定（MacroMicroに合わせた配色）
const COLORS = {
  hicp_1y: '#5DADE2',  // 水色（1年先）
  hicp_2y: '#E74C3C',  // 赤色（2年先）
  hicp_5y: '#F4D03F',  // 黄色（5年先）
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

export default function ECBSPFChart({ data }: ECBSPFChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 'default',
  })

  // 3系列のデータをマージ（発表期をX軸に）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data || !data.inflation_expectations) return []

    const hicp12m = data.inflation_expectations.hicp_12m || []
    const hicp24m = data.inflation_expectations.hicp_24m || []
    const hicpLt = data.inflation_expectations.hicp_lt || []

    // 日付をキーにしたマップを作成
    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      hicp_1y: null,
      hicp_2y: null,
      hicp_5y: null,
    })

    // 12ヶ月先（1年先）データ
    hicp12m.forEach((point) => {
      const normalizedDate = normalizeDate(point.date)
      if (!dateMap.has(normalizedDate)) {
        dateMap.set(normalizedDate, initPoint(normalizedDate))
      }
      dateMap.get(normalizedDate)!.hicp_1y = point.value
    })

    // 24ヶ月先（2年先）データ
    hicp24m.forEach((point) => {
      const normalizedDate = normalizeDate(point.date)
      if (!dateMap.has(normalizedDate)) {
        dateMap.set(normalizedDate, initPoint(normalizedDate))
      }
      dateMap.get(normalizedDate)!.hicp_2y = point.value
    })

    // 長期（5年先）データ
    hicpLt.forEach((point) => {
      const normalizedDate = normalizeDate(point.date)
      if (!dateMap.has(normalizedDate)) {
        dateMap.set(normalizedDate, initPoint(normalizedDate))
      }
      dateMap.get(normalizedDate)!.hicp_5y = point.value
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
      if (chartData[i].hicp_1y !== null) {
        return { date: chartData[i].date, value: chartData[i].hicp_1y }
      }
    }
    return null
  }, [chartData])

  const latest2y = useMemo(() => {
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].hicp_2y !== null) {
        return { date: chartData[i].date, value: chartData[i].hicp_2y }
      }
    }
    return null
  }, [chartData])

  const latest5y = useMemo(() => {
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].hicp_5y !== null) {
        return { date: chartData[i].date, value: chartData[i].hicp_5y }
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="インフレ期待（ユーロ圏・SPF）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="インフレ期待（ユーロ圏・SPF）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-spf-chart">
      <ChartContainer
        title="インフレ期待（ユーロ圏・SPF）"
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
              color: COLORS.hicp_1y,
              format: 'percent',
            },
            {
              label: '2年先',
              value: latest2y?.value,
              color: COLORS.hicp_2y,
              format: 'percent',
            },
            {
              label: '5年先',
              value: latest5y?.value,
              color: COLORS.hicp_5y,
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
                    <Tooltip title="比較ページを開く（インフレ期待）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() =>
                          window.open(
                            '/compare?s=eurozone_spf_hicp_12m&s=eurozone_spf_hicp_24m&s=eurozone_spf_hicp_lt',
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
                        dataKey: 'hicp_1y',
                        color: COLORS.hicp_1y,
                        name: '1年先',
                      },
                      {
                        dataKey: 'hicp_2y',
                        color: COLORS.hicp_2y,
                        name: '2年先',
                      },
                      {
                        dataKey: 'hicp_5y',
                        color: COLORS.hicp_5y,
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
