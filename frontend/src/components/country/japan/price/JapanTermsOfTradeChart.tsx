/**
 * 日本 交易条件（Terms of Trade）チャートコンポーネント
 *
 * 交易条件 = 輸出物価指数 / 輸入物価指数 × 100
 * - 100を超えると交易条件が改善（輸出価格が輸入価格より上昇）
 * - 100を下回ると交易条件が悪化（輸入価格が輸出価格より上昇）
 *
 * データソース:
 * - BOJ (日本銀行) CGPI ZIPファイル
 * - URL: https://www.stat-search.boj.or.jp/ssi/docs/info/cgpi_m_jp.zip
 *
 * 発表スケジュール:
 * - 毎月10日〜18日頃 8:50 JST（CGPIと同一）
 */

import { useEffect, useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import {
  CHART_COLORS,
} from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface TermsOfTradeDataPoint {
  date: string
  value: number
  terms_of_trade: number
  export_price_index: number
  import_price_index: number
}

interface TermsOfTradeResponse {
  data: TermsOfTradeDataPoint[]
  latest: TermsOfTradeDataPoint | null
  metadata: {
    source: string
    source_url: string
    description: string
    unit: string
    frequency: string
  }
  next_release?: {
    date: string
    datetime_jst: string
    time_jst?: string
    label: string
  }
  cached: boolean
  source: string
  last_updated: string
}

interface ChartDataPoint {
  date: string
  terms_of_trade: number | null
  export_price_index: number | null
  import_price_index: number | null
}

// =============================================================================
// API呼び出し関数
// =============================================================================

async function fetchTermsOfTradeData(): Promise<TermsOfTradeResponse | null> {
  try {
    const response = await fetch('/api/japan/terms-of-trade')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return await response.json()
  } catch (error) {
    console.error('Failed to fetch terms of trade data:', error)
    return null
  }
}

// =============================================================================
// コンポーネント
// =============================================================================

export default function JapanTermsOfTradeChart() {
  const [data, setData] = useState<TermsOfTradeResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(10)

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      const result = await fetchTermsOfTradeData()
      setData(result)
      setLoading(false)
    }
    loadData()
  }, [])

  // チャート用データに変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    return data.data.map((item) => ({
      date: item.date,
      terms_of_trade: item.terms_of_trade,
      export_price_index: item.export_price_index,
      import_price_index: item.import_price_index,
    }))
  }, [data])

  // ソートされたデータ
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // ローディング
  if (loading) {
    return <LoadingChart title="交易条件" />
  }

  // データなし
  if (!data || !data.data || data.data.length === 0) {
    return (
      <ChartContainer title="交易条件" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latestValue = data.latest

  // 線の設定
  const linesConfig = [
    {
      dataKey: 'terms_of_trade',
      name: '交易条件',
      color: CHART_COLORS.primary,
      strokeWidth: 2,
    },
  ]

  return (
    <div id="japan-terms-of-trade-chart">
      <ChartContainer
        title="交易条件"
        showPeriodSelector={false}
        dataSource="日本銀行（BOJ）"
        sourceUrl="https://www.stat-search.boj.or.jp/ssi/docs/info/cgpi_m_jp.zip"
        handbookId="terms-of-trade"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="交易条件"
          value={latestValue?.terms_of_trade}
          valueColor={latestValue && latestValue.terms_of_trade >= 100 ? CHART_COLORS.positive : CHART_COLORS.negative}
          date={latestValue?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="number"
          decimals={2}
          unit=""
        />

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
                        onClick={() => window.open('/compare?s=japan_terms_of_trade', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={linesConfig}
                    yAxisFormatter={(v) => `${v.toFixed(1)}`}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                    tooltipValueFormatter={(v) => v.toFixed(2)}
                    showZeroLine={false}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="japan_cgpi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
