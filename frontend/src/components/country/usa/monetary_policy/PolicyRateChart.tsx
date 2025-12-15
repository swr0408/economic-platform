import { useState, useEffect, useMemo } from 'react'
import { Tooltip } from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import { fetchPolicyRate } from '../../../../utils/api'

interface PolicyRateChartData {
  date: string
  value: number
  rate: number
  [key: string]: string | number | null | undefined
}

export default function PolicyRateChart() {
  const [policyRateData, setPolicyRateData] = useState<PolicyRateChartData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')

  useEffect(() => {
    const loadPolicyRateData = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchPolicyRate()

        // データを変換
        const chartData: PolicyRateChartData[] = data.map((item) => ({
          date: item.date,
          value: item.rate,
          rate: item.rate,
        }))

        // 日付でソート（古い順）
        chartData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

        setPolicyRateData(chartData)
      } catch (err) {
        console.error('Error loading policy rate data:', err)
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }

    loadPolicyRateData()
  }, [])

  const formatPercentage = (value: number) => {
    return `${value.toFixed(2)}%`
  }

  const formatMonthLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
  }

  // 期間に基づいてデータをフィルタリング
  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all' || policyRateData.length === 0) {
      return policyRateData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      // デフォルトは2020年から
      cutoffDate.setFullYear(2020, 0, 1)
    } else {
      // 指定年数前から
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return policyRateData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [policyRateData, selectedPeriod])

  const hasData = useMemo(() => policyRateData.length > 0, [policyRateData])

  if (loading) {
    return <LoadingChart title="Federal Funds Target Rate" />
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '50px', color: '#ff4d4f' }}>Error: {error}</div>
    )
  }

  if (!hasData) {
    return (
      <ChartContainer title="Federal Funds Target Rate" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  return (
    <div id="policy-rate-chart">
      <ChartContainer
        title="政策金利"
        showPeriodSelector={false}
        dataSource="Federal Reserve"
      >
        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        <ZoomableChart
          data={filteredData}
          dataKey="rate"
          color="#1890ff"
          name="政策金利"
          height={450}
          tickFormatter={formatPercentage}
          xAxisTickFormatter={formatMonthLabel}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={false}
          showDefaultTooltip={false}
          domain={['dataMin - 0.25', 'dataMax + 0.25']}
        >
          <Tooltip
            labelFormatter={(value: string | number) => formatMonthLabel(String(value))}
            formatter={(value: number, name: string) => [formatPercentage(value), name]}
          />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
