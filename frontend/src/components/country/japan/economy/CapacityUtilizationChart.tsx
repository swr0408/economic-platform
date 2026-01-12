/**
 * 稼働率指数チャートコンポーネント（日本）
 *
 * データソース: 経済産業省 (METI)
 * URL: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_ngsm1j.xlsx
 * 更新: 月次（IIPと同時）
 *
 * 表示:
 * - 稼働率指数の時系列グラフ（LineChart）
 */
import { useState, useEffect, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { useHiddenSeries } from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import {
  fetchJapanCapacityUtilizationData,
  formatCapacityDate,
  type JapanCapacityUtilizationDataPoint,
} from '../../../../api/japanCapacityUtilizationApi'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  value: number | null
}

// グラフの色
const COLORS = {
  value: '#1890ff',
}

// =============================================================================
// ヘルパー関数
// =============================================================================

// 期間フィルタリング
const filterByPeriod = (
  data: ChartDataPoint[],
  period: PeriodValue,
  defaultStartYear: number = 2018
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

export default function CapacityUtilizationChart() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rawData, setRawData] = useState<JapanCapacityUtilizationDataPoint[]>([])
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データ取得
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const response = await fetchJapanCapacityUtilizationData()

        if (response.error) {
          setError(response.error)
        } else {
          setRawData(response.data)
        }
      } catch (err) {
        console.error('Error fetching Capacity Utilization data:', err)
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
      .map(item => ({
        date: item.date,
        value: item.value,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [rawData])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    return filterByPeriod(chartData, currentPeriod, 2010)
  }, [chartData, currentPeriod])

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestData = rawData.length > 0 ? rawData[0] : null

  if (loading) {
    return <LoadingChart title="稼働率指数（Capacity Utilization）" />
  }

  if (error) {
    return (
      <ChartContainer title="稼働率指数（Capacity Utilization）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
          {error}
        </div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="稼働率指数（Capacity Utilization）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="japan-capacity-utilization-chart">
      <ChartContainer
        title="稼働率指数"
        showPeriodSelector={false}
        dataSource="経済産業省"
        sourceUrl="https://www.meti.go.jp/statistics/tyo/iip/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latestData?.value}
          valueColor={COLORS.value}
          date={latestData?.date}
          dateFormatter={formatCapacityDate}
          format="number"
          unit="%"
        />

        {/* 期間セレクター */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=japan_capacity_utilization', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'value', color: COLORS.value, name: '稼働率指数', hide: hiddenSeries.has('value') },
          ]}
          yAxisFormatter={(v) => `${v}%`}
          yDomain={['dataMin - 1', 'dataMax + 1']}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
