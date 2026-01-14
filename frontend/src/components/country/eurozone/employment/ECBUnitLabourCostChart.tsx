/**
 * ECB労働コスト指数チャートコンポーネント
 *
 * ECB Data APIから労働コスト指数データを取得し、表示
 *
 * データ:
 * - Unit Labour Cost (労働コスト指数)
 * - 前年比 (YoY) 変化率
 * - 前期比 (QoQ) 変化率
 *
 * データソース:
 * - European Central Bank (ECB) - MNA Dataflow
 *
 * 発表スケジュール:
 * - 3月・6月・9月・12月: 13日〜21日
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

import type { ECBUnitLabourCostData } from '../../../../hooks/useDashboardData'

interface ECBUnitLabourCostChartProps {
  data: ECBUnitLabourCostData | null
}

interface ChartDataPoint {
  date: string
  yoy: number | null
  qoq: number | null
  [key: string]: unknown
}

type ViewMode = 'yoy' | 'qoq_table' | 'qoq_chart'

// グラフの色
const COLORS = {
  yoy: '#1890ff',
  qoq: '#52c41a',
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

export default function ECBUnitLabourCostChart({ data }: ECBUnitLabourCostChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('yoy')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<number | 'all' | 'default'>('default')

  // propsのデータをチャート用に変換（YoYとQoQをマージ）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const yoyData = data.unit_labour_cost_yoy || []
    const qoqData = data.unit_labour_cost_qoq || []

    // 日付をキーにしたマップを作成
    const dataMap = new Map<string, ChartDataPoint>()

    for (const item of yoyData) {
      if (item.value !== null) {
        dataMap.set(item.date, {
          date: item.date,
          yoy: item.value,
          qoq: null,
        })
      }
    }

    for (const item of qoqData) {
      if (item.value !== null) {
        const existing = dataMap.get(item.date)
        if (existing) {
          existing.qoq = item.value
        } else {
          dataMap.set(item.date, {
            date: item.date,
            yoy: null,
            qoq: item.value,
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
    if (!data?.unit_labour_cost_yoy?.length) return null
    return data.unit_labour_cost_yoy[data.unit_labour_cost_yoy.length - 1]
  }, [data])

  if (data === null) {
    return <LoadingChart title="労働コスト指数（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="労働コスト指数（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-unit-labour-cost-chart">
      <ChartContainer
        title="労働コスト指数（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="ECB"
        sourceUrl="https://ec.europa.eu/eurostat/en/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=ElGw9c6n&text=labour+costs"
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
                          onClick={() => window.open('/compare?s=ecb_unit_labour_cost_yoy', '_blank')}
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
                <MarketImpactTab indicatorId="ecb_unit_labour_cost" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
