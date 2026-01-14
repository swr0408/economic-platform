/**
 * ECB労働生産性チャートコンポーネント
 *
 * ECB Data APIから労働生産性データを取得し、表示
 *
 * データ:
 * - Labor Productivity per Hour Worked (時間あたり労働生産性)
 * - Labor Productivity per Person (就業者あたり労働生産性)
 * - 前年比 (YoY) 変化率
 *
 * データソース:
 * - European Central Bank (ECB) - MNA Dataflow
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
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ECBLaborProductivityData } from '../../../../hooks/useDashboardData'

interface ECBLaborProductivityChartProps {
  data: ECBLaborProductivityData | null
}

interface ChartDataPoint {
  date: string
  perHour: number | null
  perPerson: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  perHour: '#1890ff',
  perPerson: '#52c41a',
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

export default function ECBLaborProductivityChart({ data }: ECBLaborProductivityChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<number | 'all' | 'default'>('default')

  // propsのデータをチャート用に変換（時間あたりと就業者あたりをマージ）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const perHourYoY = data.per_hour_yoy || []
    const perPersonYoY = data.per_person_yoy || []

    // 日付をキーにしたマップを作成
    const dataMap = new Map<string, ChartDataPoint>()

    for (const item of perHourYoY) {
      if (item.value !== null) {
        dataMap.set(item.date, {
          date: item.date,
          perHour: item.value,
          perPerson: null,
        })
      }
    }

    for (const item of perPersonYoY) {
      if (item.value !== null) {
        const existing = dataMap.get(item.date)
        if (existing) {
          existing.perPerson = item.value
        } else {
          dataMap.set(item.date, {
            date: item.date,
            perHour: null,
            perPerson: item.value,
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

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestPerHour = useMemo(() => {
    if (!data?.per_hour_yoy?.length) return null
    return data.per_hour_yoy[data.per_hour_yoy.length - 1]
  }, [data])

  const latestPerPerson = useMemo(() => {
    if (!data?.per_person_yoy?.length) return null
    return data.per_person_yoy[data.per_person_yoy.length - 1]
  }, [data])

  if (data === null) {
    return <LoadingChart title="労働生産性（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="労働生産性（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-labor-productivity-chart">
      <ChartContainer
        title="労働生産性（ユーロ圏・前年比）"
        showPeriodSelector={false}
        dataSource="ECB"
        sourceUrl="https://ec.europa.eu/eurostat/en/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_text=GDP&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=FdY2UEfx&text=employment"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="就業時間ベース"
          value={latestPerHour?.value}
          valueColor={COLORS.perHour}
          subLabel="就業者ベース"
          subValue={latestPerPerson?.value}
          subValueColor={COLORS.perPerson}
          date={latestPerHour?.date}
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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ecb_labor_productivity_per_hour_yoy&s=ecb_labor_productivity_per_person_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'perHour', color: COLORS.perHour, name: '就業時間ベース' },
                      { dataKey: 'perPerson', color: COLORS.perPerson, name: '就業者ベース' },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    showZeroLine={true}
                  />
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
