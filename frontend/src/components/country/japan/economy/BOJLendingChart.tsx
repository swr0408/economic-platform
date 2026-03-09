/**
 * 日銀貸出動向チャート
 *
 * データソース: 日本銀行 統計検索サイト
 * データコード: FAAPOBAL1（貸出動向・銀行計）
 * 更新: 毎月（月末から翌月初に公表）
 *
 * 表示: 前年比（%）
 */
import { useState, useEffect, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// USA共通モジュールを流用
import {
  usePeriodFiltering,
  formatPercent,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
} from '../../usa/common/ChartComponents'

import {
  fetchBOJLendingYoYData,
  type BOJLendingDataPoint,
} from '../../../../api/bojLendingApi'

// チャートデータ型
interface LendingChartData {
  date: string
  value: number
  originalDate: string
  [key: string]: string | number | null | undefined
}

// グラフの色
const COLORS = {
  yoy: '#3b82f6',  // 青
}

/**
 * APIから取得した前年比データをチャート用に変換
 */
function transformToChartData(data: BOJLendingDataPoint[]): LendingChartData[] {
  return data.map((item) => {
    const [year, month] = item.date.split('-')
    const dateObj = new Date(parseInt(year), parseInt(month) - 1, 1)
    return {
      date: dateObj.toISOString(),
      value: item.value,
      originalDate: item.date,
    }
  })
}

const BOJLendingChart: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [yoyData, setYoyData] = useState<BOJLendingDataPoint[]>([])
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(20)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const response = await fetchBOJLendingYoYData()
        if (response.error) {
          setError(response.error)
        } else {
          setYoyData(response.data)
        }
      } catch (err) {
        console.error('Error fetching BOJ Lending data:', err)
        setError('データの取得に失敗しました')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // 月日付フォーマット（YYYY-MM -> YYYY/MM）
  const formatMonthLabel = (dateStr: string): string => {
    try {
      return dateStr.replace('-', '/')
    } catch {
      return dateStr
    }
  }

  // チャートデータに変換
  const yoyChartData = useMemo<LendingChartData[]>(() => {
    if (!yoyData || yoyData.length === 0) return []
    return transformToChartData(yoyData)
  }, [yoyData])

  // formatPercent共通関数を使用（小数点1桁）
  const formatPercentage = (value: number) => formatPercent(value, 1)

  // 期間フィルタリング
  const filteredYoYData = usePeriodFiltering(yoyChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = yoyChartData.length > 0

  if (loading) {
    return <LoadingChart title="貸出動向（前年比）" />
  }

  if (error) {
    return (
      <ChartContainer title="貸出動向（前年比）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>
          {error}
        </div>
      </ChartContainer>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="貸出動向（前年比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestYoY = yoyChartData.length > 0 ? yoyChartData[yoyChartData.length - 1] : null

  return (
    <div id="japan-boj-lending-chart">
      <ChartContainer
        title="貸出動向（前年比）"
        showPeriodSelector={false}
        dataSource="日本銀行"
        sourceUrl="https://www.stat-search.boj.or.jp/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="前年比"
          value={latestYoY?.value}
          valueColor={COLORS.yoy}
          date={latestYoY?.originalDate}
          dateFormatter={formatMonthLabel}
          format="percent"
          decimals={1}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=japan_boj_lending', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <ZoomableChart
                    data={filteredYoYData}
                    dataKey="value"
                    color={COLORS.yoy}
                    name="貸出動向（前年比）"
                    height={450}
                    tickFormatter={formatPercentage}
                    tooltipFormatter={formatPercentage}
                    tooltipLabelFormatter={(dateStr) => {
                      const date = new Date(dateStr)
                      return `${date.getFullYear()}年${date.getMonth() + 1}月`
                    }}
                    xAxisTickFormatter={(dateStr) => {
                      const date = new Date(dateStr)
                      return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
                    }}
                    enableDynamicTicks={true}
                    showZeroLine={true}
                    showFiftyLine={false}
                    connectNulls={true}
                    hideLegend={true}
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

export default BOJLendingChart
