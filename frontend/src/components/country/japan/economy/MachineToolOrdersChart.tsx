/**
 * 工作機械受注チャートコンポーネント（日本）
 *
 * データソース: 日本工作機械工業会 (JMTBA)
 * 更新: 月次
 *
 * 表示:
 * - 前年比グラフ
 */
import { useState, useEffect, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { TEXT_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  fetchMachineToolOrders,
  type MachineToolOrdersDataPoint,
} from '../../../../utils/japan/machineToolOrdersApi'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  value: number | null
}

// グラフの色
const COLORS = {
  yoy: '#1890ff',
}

// 次回発表日時のフォーマット
// next_release はオブジェクト形式 { datetime_jst: "2026-02-12T15:00:00+09:00", ... } または文字列
const formatNextRelease = (nextRelease: string | { datetime_jst?: string; date?: string } | null | undefined): string | null => {
  if (!nextRelease) return null
  try {
    // オブジェクト形式の場合
    if (typeof nextRelease === 'object') {
      const dateStr = nextRelease.datetime_jst || nextRelease.date
      if (!dateStr) return null
      const dt = new Date(dateStr)
      const month = dt.getMonth() + 1
      const day = dt.getDate()
      const hours = dt.getHours().toString().padStart(2, '0')
      const minutes = dt.getMinutes().toString().padStart(2, '0')
      return `${month}/${day} ${hours}:${minutes}`
    }
    // 文字列形式の場合
    const dt = new Date(nextRelease)
    const month = dt.getMonth() + 1
    const day = dt.getDate()
    const hours = dt.getHours().toString().padStart(2, '0')
    const minutes = dt.getMinutes().toString().padStart(2, '0')
    return `${month}/${day} ${hours}:${minutes}`
  } catch {
    return null
  }
}

// 日付フォーマット
const formatDate = (dateStr: string): string => {
  try {
    const dt = new Date(dateStr)
    return `${dt.getFullYear()}年${dt.getMonth() + 1}月`
  } catch {
    return dateStr
  }
}

// =============================================================================
// ヘルパー関数
// =============================================================================

// 期間フィルタリング
const filterByPeriod = (
  data: ChartDataPoint[],
  period: PeriodValue,
  defaultStartYear: number = 2015
): ChartDataPoint[] => {
  if (period === 'all') {
    return data
  }

  let cutoffDate: Date
  if (period === 'default') {
    cutoffDate = new Date(defaultStartYear, 0, 1)
  } else if (typeof period === 'number') {
    cutoffDate = new Date()
    cutoffDate.setFullYear(cutoffDate.getFullYear() - period)
  } else {
    cutoffDate = new Date(defaultStartYear, 0, 1)
  }

  return data.filter(item => {
    const itemDate = new Date(item.date)
    return itemDate >= cutoffDate
  })
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function MachineToolOrdersChart() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rawData, setRawData] = useState<MachineToolOrdersDataPoint[]>([])
  const [nextRelease, setNextRelease] = useState<string | { datetime_jst?: string; date?: string } | null>(null)
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ取得
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const response = await fetchMachineToolOrders()

        if (response.error) {
          setError(response.error)
        } else {
          setRawData(response.data ?? [])
          if (response.next_release) {
            setNextRelease(response.next_release)
          }
        }
      } catch (err) {
        console.error('Error fetching Machine Tool Orders data:', err)
        setError('データの取得に失敗しました')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // チャートデータに変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    return rawData
      .filter(item => item.value !== null)
      .map(item => ({
        date: item.date,
        value: item.value,
      }))
  }, [rawData])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod, 2015)
  }, [chartData, currentPeriod])

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestData = rawData.length > 0 ? rawData[rawData.length - 1] : null

  if (loading) {
    return <LoadingChart title="工作機械受注" />
  }

  if (error) {
    return (
      <ChartContainer title="工作機械受注" showPeriodSelector={false} showDataSource={false} handbookId="machine-tool-orders">
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
          {error}
        </div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="工作機械受注" showPeriodSelector={false} showDataSource={false} handbookId="machine-tool-orders">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="machine-tool-orders-chart">
      <ChartContainer
        title="工作機械受注（前年比）"
        showPeriodSelector={false}
        dataSource="日本工作機械工業会"
        sourceUrl="https://www.jmtba.or.jp/statistics/"
        handbookId="machine-tool-orders"
      >
        {/* 最新値表示（統合ボックス） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 左側: 最新値 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {latestData?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDate(latestData.date)}
              </span>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                前年比:
              </span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.yoy }}>
                {latestData?.value?.toFixed(1) ?? '-'}%
              </span>
            </div>
          </div>

          {/* 右側: 次回発表 */}
          {nextRelease && formatNextRelease(nextRelease) && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              color: TEXT_COLORS.secondary,
            }}>
              <CalendarOutlined />
              <span>次回発表: {formatNextRelease(nextRelease)}</span>
            </div>
          )}
        </div>

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
                        onClick={() => window.open('/compare?s=japan_machine_tool_orders_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* グラフ表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.yoy, name: '工作機械受注（前年比）', hide: hiddenSeries.has('value') },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="japan_machine_tool_orders_yoy" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
