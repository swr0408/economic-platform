/**
 * ECB雇用者数変化チャートコンポーネント
 *
 * FMPから雇用者数変化データを取得し、表示
 *
 * データ:
 * - Employment Change QoQ (前期比)
 * - Employment Change YoY (前年比)
 *
 * データソース:
 * - FMP Economic Calendar
 *
 * 発表スケジュール:
 * - 2月・5月・8月・11月: 10日〜18日
 * - 3月・6月・9月・12月: 5日〜9日
 * - 発表時刻: 18:00-18:10 CET
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useQuarterlyTableData,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ECBEmploymentData } from '../../../../hooks/useDashboardData'

interface ECBEmploymentChartProps {
  data: ECBEmploymentData | null
}

interface ChartDataPoint {
  date: string
  qoq: number | null
  yoy: number | null
  [key: string]: unknown
}

type ViewMode = 'yoy' | 'qoq_table' | 'qoq_chart'

// グラフの色
const COLORS = {
  qoq: '#52c41a',
  yoy: '#1890ff',
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
    // デフォルトは全データ表示（四半期データは少ないため）
    return data
  } else {
    cutoffDate = new Date(now.getFullYear() - selectedPeriod, now.getMonth(), 1)
  }

  return data.filter((item) => {
    const itemDate = parseQuarterDate(item.date)
    return itemDate >= cutoffDate
  })
}

export default function ECBEmploymentChart({ data }: ECBEmploymentChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<number | 'all' | 'default'>('all')

  // propsのデータをチャート用に変換（QoQとYoYをマージ）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const qoqData = data.employment_qoq || []
    const yoyData = data.employment_yoy || []

    // 日付をキーにしたマップを作成
    const dataMap = new Map<string, ChartDataPoint>()

    for (const item of qoqData) {
      if (item.value !== null) {
        dataMap.set(item.date, {
          date: item.date,
          qoq: item.value,
          yoy: null,
        })
      }
    }

    for (const item of yoyData) {
      if (item.value !== null) {
        const existing = dataMap.get(item.date)
        if (existing) {
          existing.yoy = item.value
        } else {
          dataMap.set(item.date, {
            date: item.date,
            qoq: null,
            yoy: item.value,
          })
        }
      }
    }

    // 四半期日付でソート
    return Array.from(dataMap.values()).sort((a, b) =>
      parseQuarterDate(a.date).getTime() - parseQuarterDate(b.date).getTime()
    )
  }, [data])

  // 期間フィルタリング（四半期データ用）
  const filteredData = useMemo(() =>
    filterQuarterlyData(chartData, currentPeriod),
    [chartData, currentPeriod]
  )

  // 四半期テーブル用データ（前期比）
  const qoqTableData = useQuarterlyTableData(chartData, (item) => item.qoq)

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestYoY = useMemo(() => {
    if (!data?.employment_yoy?.length) return null
    return data.employment_yoy[data.employment_yoy.length - 1]
  }, [data])

  if (data === null) {
    return <LoadingChart title="雇用者数変化（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="雇用者数変化（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-employment-chart">
      <ChartContainer
        title="雇用者数変化（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="ECB"
        sourceUrl="https://ec.europa.eu/eurostat/en/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_text=GDP&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=FdY2UEfx&text=employment"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latestYoY?.value}
          valueColor={COLORS.yoy}
          date={latestYoY?.date}
          nextRelease={data.next_release}
          format="percent"
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
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode)}
                    options={[
                      { mode: 'yoy', label: '前年比' },
                      { mode: 'qoq_table', label: '前期比テーブル' },
                      { mode: 'qoq_chart', label: '前期比グラフ' },
                    ]}
                  />

                  {/* 期間セレクター */}
                  {(viewMode === 'yoy' || viewMode === 'qoq_chart') && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s=ecb_employment_qoq&s=ecb_employment_yoy', '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* コンテンツ表示 */}
                  {viewMode === 'qoq_table' && (
                    <QuarterlyTable
                      data={qoqTableData}
                      showLegend={false}
                      helperText="※ 直近10年間の前期比データ（単位: %）"
                    />
                  )}

                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: '前年比' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      showZeroLine={true}
                    />
                  )}

                  {viewMode === 'qoq_chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'qoq', color: COLORS.qoq, name: '前期比' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ecb_employment" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
