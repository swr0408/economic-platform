import { useState, useEffect, useMemo } from 'react'
import { Tooltip } from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import { fetchTermPremium, type TermPremiumData } from '../../../../utils/usa/monetary_policyApi'
import { fetchKWTermPremium, type FREDSeriesData } from '../../../../utils/usa/fredApi'

interface TermPremiumChartData {
  date: string
  value: number  // ZoomableChart requires this (mapped to yield_10y)
  yield_10y: number | null         // 10年債利回り (NY Fed ACM)
  acm_term_premium: number | null  // ACMタームプレミアム (NY Fed)
  kw_term_premium: number | null   // KWタームプレミアム (FRED)
  expected_rate: number | null     // 期待短期金利 (NY Fed)
  [key: string]: string | number | null | undefined
}

export default function TermPremiumChart() {
  const [chartData, setChartData] = useState<TermPremiumChartData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      setError(null)
      try {
        // 並行してデータを取得
        const [acmData, kwData] = await Promise.all([
          fetchTermPremium(),
          fetchKWTermPremium().catch(() => [] as FREDSeriesData[])  // KWデータがなくても続行
        ])

        // KWデータをMapに変換（日付でルックアップ用）
        const kwDataMap = new Map<string, number>()
        kwData.forEach((item) => {
          kwDataMap.set(item.date, item.value)
        })

        // ACMデータをベースにマージ
        const mergedData: TermPremiumChartData[] = acmData.map((item: TermPremiumData) => {
          const kwValue = kwDataMap.get(item.date) ?? null
          return {
            date: item.date,
            value: item.yield_10y ?? 0,
            yield_10y: item.yield_10y,
            acm_term_premium: item.term_premium,
            kw_term_premium: kwValue,
            expected_rate: item.expected_rate,
          }
        })

        // 日付でソート（古い順）
        mergedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

        setChartData(mergedData)
      } catch (err) {
        console.error('Error loading term premium data:', err)
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  const formatPercentage = (value: number) => {
    if (value === null || value === undefined) return '-'
    return `${value.toFixed(2)}%`
  }

  const formatDateLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`
  }

  // 期間に基づいてデータをフィルタリング
  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all' || chartData.length === 0) {
      return chartData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      // デフォルトは2020年から
      cutoffDate.setFullYear(2020, 0, 1)
    } else {
      // 指定年数前から
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return chartData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [chartData, selectedPeriod])

  const hasData = useMemo(() => chartData.length > 0, [chartData])

  // X軸の表示間隔を動的に計算（データポイント数に基づく）
  const xAxisInterval = useMemo(() => {
    const dataLength = filteredData.length
    if (dataLength <= 30) return 0  // 30データポイント以下なら全て表示
    if (dataLength <= 60) return Math.floor(dataLength / 15)  // 約15ラベル表示
    if (dataLength <= 120) return Math.floor(dataLength / 12)  // 約12ラベル表示
    if (dataLength <= 365) return Math.floor(dataLength / 10)  // 約10ラベル表示
    return Math.floor(dataLength / 8)  // それ以上は約8ラベル表示
  }, [filteredData.length])

  if (loading) {
    return <LoadingChart title="タームプレミアム分解" />
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '50px', color: '#ff4d4f' }}>Error: {error}</div>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="タームプレミアム分解" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  // 追加ライン設定（4ラインチャート）
  const additionalLines = [
    {
      dataKey: 'acm_term_premium',
      color: '#722ed1',  // 紫
      name: 'ACMタームプレミアム',
    },
    {
      dataKey: 'kw_term_premium',
      color: '#fa8c16',  // オレンジ
      name: 'KWタームプレミアム',
    },
    {
      dataKey: 'expected_rate',
      color: '#52c41a',  // 緑
      name: '期待短期金利',
    },
  ]

  return (
    <div id="term-premium-chart">
      <ChartContainer
        title="タームプレミアム"
        showPeriodSelector={false}
        source="NY Fed, FRED"
      >
        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        <ZoomableChart
          data={filteredData}
          dataKey="yield_10y"
          color="#1890ff"
          name="10年債利回り"
          height={450}
          tickFormatter={formatPercentage}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={false}
          showDefaultTooltip={false}
          domain={['dataMin - 0.5', 'dataMax + 0.5']}
          additionalLines={additionalLines}
          initialHiddenLines={['kw_term_premium']}
          xAxisInterval={xAxisInterval}
        >
          <Tooltip
            labelFormatter={(value: string | number) => formatDateLabel(String(value))}
            formatter={(value: number, name: string) => [formatPercentage(value), name]}
          />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
