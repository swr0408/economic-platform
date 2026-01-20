/**
 * UK BRC小売売上高チャートコンポーネント
 *
 * データ:
 * - BRC Retail Sales Monitor（前年比）
 *
 * データソース:
 * - British Retail Consortium (BRC)
 *
 * 発表スケジュール:
 * - 毎月（通常3日〜20日）
 * - 8:01-9:11 ロンドン時間
 */
import { useState, useMemo, useCallback, useEffect } from 'react'
import { Tabs, Button, Tooltip, Spin, Alert, Typography, Collapse } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import { fetchBRCCommentary, type BRCCommentaryData } from '../../../../utils/uk/brcCommentaryApi'

import type { BRCRetailSalesData } from '../../../../hooks/useDashboardData'
import type { PeriodType } from '../../usa/common/useChartData'

const { Text, Paragraph } = Typography

interface BRCRetailSalesChartProps {
  data: BRCRetailSalesData | null
}

interface ChartDataPoint {
  date: string
  value: number
  [key: string]: unknown
}

// グラフの色
const CHART_COLOR = '#e74c3c'

export default function BRCRetailSalesChart({ data }: BRCRetailSalesChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()
  const [commentary, setCommentary] = useState<BRCCommentaryData | null>(null)
  const [commentaryLoading, setCommentaryLoading] = useState(true)

  // コメンタリーを取得
  useEffect(() => {
    const loadCommentary = async () => {
      try {
        setCommentaryLoading(true)
        const commentaryData = await fetchBRCCommentary()
        setCommentary(commentaryData)
      } catch (err) {
        console.error('Error loading BRC commentary:', err)
        setCommentary(null)
      } finally {
        setCommentaryLoading(false)
      }
    }

    loadCommentary()
  }, [])

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data
      .filter(point => point.value !== null)
      .map(point => ({
        date: point.date,
        value: point.value as number,
      }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 期間変更ハンドラ
  const handlePeriodChange = useCallback((period: PeriodType) => {
    setSelectedPeriod(period)
  }, [])

  // データ比較ページを開く
  const handleCompare = useCallback(() => {
    window.open('/compare?s=uk_brc_retail_sales_yoy&s=uk_retail_sales_yoy', '_blank')
  }, [])

  if (data === null) {
    return <LoadingChart title="BRC小売売上高（前年比）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="BRC小売売上高（前年比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // コメンタリーのCollapse items生成
  const commentaryItems = commentary?.commentaries?.map((item, index) => ({
    key: String(index),
    label: item.speaker || `コメント ${index + 1}`,
    children: (
      <Paragraph style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, margin: 0 }}>
        {item.ja}
      </Paragraph>
    ),
  })) || []

  // コメンタリータブのタイトル
  const commentaryTabLabel = commentary?.data_year && commentary?.data_month
    ? `コメンタリー（${commentary.data_year}/${commentary.data_month}）`
    : 'コメンタリー'

  return (
    <div id="uk-brc-retail-sales-chart">
      <ChartContainer
        title="BRC小売売上高（前年比）"
        showPeriodSelector={false}
        dataSource="BRC"
        sourceUrl="https://brc.org.uk/market-intelligence/publications/monitors/retail-sales-monitor/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={CHART_COLOR}
          date={latest?.date}
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
                    <PeriodSelector onPeriodChange={handlePeriodChange} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={handleCompare}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      {
                        dataKey: 'value',
                        color: CHART_COLOR,
                        name: 'BRC小売売上高（前年比）',
                        hide: hiddenSeries.has('value')
                      },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    onLegendClick={handleLegendClick}
                    yDomain={['dataMin - 2', 'dataMax + 2']}
                  />
                </>
              ),
            },
            {
              key: 'commentary',
              label: commentaryTabLabel,
              children: (
                <div style={{ minHeight: 200 }}>
                  {commentaryLoading ? (
                    <div style={{ textAlign: 'center', padding: 40 }}>
                      <Spin tip="コメンタリーを読み込み中..." />
                    </div>
                  ) : commentary?.error ? (
                    <Alert
                      message="コメンタリーの取得に失敗しました"
                      description={commentary.error}
                      type="warning"
                      showIcon
                    />
                  ) : commentary?.commentaries && commentary.commentaries.length > 0 ? (
                    <div>
                      {commentary.commentaries.length === 1 ? (
                        // 1つだけの場合は折りたたみなし
                        <Paragraph style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
                          {commentary.commentaries[0].ja}
                        </Paragraph>
                      ) : (
                        // 複数の場合は折りたたみ表示
                        <Collapse
                          defaultActiveKey={['0']}
                          items={commentaryItems}
                        />
                      )}
                      {commentary.url && (
                        <div style={{ marginTop: 16, fontSize: 12, color: '#888' }}>
                          Data source:{' '}
                          <a href={commentary.url} target="_blank" rel="noopener noreferrer">
                            British Retail Consortium
                          </a>
                        </div>
                      )}
                    </div>
                  ) : (
                    <Text type="secondary">コメンタリーは現在利用できません</Text>
                  )}
                </div>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="brc_retail_sales" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
