import { useState, useMemo } from 'react'
import { Tooltip } from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 潜在成長率データの型定義
interface PotentialGDPItem {
  date: string
  value: number
}

interface PotentialGDPData {
  real: PotentialGDPItem[]
  nominal: PotentialGDPItem[]
}

interface PotentialGDPChartProps {
  data: PotentialGDPData | null
}

interface ChartDataPoint {
  date: string
  value: number
  realGDP: number | null
  nominalGDP: number | null
  [key: string]: string | number | null | undefined
}

export default function PotentialGDPChart({ data }: PotentialGDPChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<number | 'all' | 'default'>('default')

  // 名目・実質データを統合
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const realData = data.real || []
    const nominalData = data.nominal || []

    // 全ての日付を収集
    const allDates = new Set<string>()
    realData.forEach((d) => allDates.add(d.date))
    nominalData.forEach((d) => allDates.add(d.date))

    // 日付でソート
    const sortedDates = Array.from(allDates).sort(
      (a, b) => new Date(a).getTime() - new Date(b).getTime()
    )

    // データをマージ
    return sortedDates.map((date) => {
      const realPoint = realData.find((d) => d.date === date)
      const nominalPoint = nominalData.find((d) => d.date === date)

      return {
        date,
        value: realPoint?.value ?? 0, // ZoomableChartのdataKey用
        realGDP: realPoint?.value ?? null,
        nominalGDP: nominalPoint?.value ?? null,
      }
    })
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all' || chartData.length === 0) {
      return chartData
    }

    const cutoffDate = new Date()

    if (selectedPeriod === 'default') {
      // デフォルトは2000年から
      cutoffDate.setFullYear(2000, 0, 1)
    } else {
      // 指定年数前から
      cutoffDate.setFullYear(cutoffDate.getFullYear() - selectedPeriod)
    }

    return chartData.filter((item) => {
      const itemDate = new Date(item.date)
      return itemDate >= cutoffDate
    })
  }, [chartData, selectedPeriod])

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="名目潜在成長率 / 実質潜在成長率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="名目潜在成長率 / 実質潜在成長率" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          データが利用できません
        </div>
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestReal = data.real?.length > 0 ? data.real[data.real.length - 1] : null
  const latestNominal = data.nominal?.length > 0 ? data.nominal[data.nominal.length - 1] : null

  const formatPercentage = (value: number | null) => {
    if (value === null || value === undefined) return '-'
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(2)}%`
  }

  const formatQuarterLabel = (dateStr: string): string => {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    const year = date.getFullYear()
    const quarter = Math.floor(date.getMonth() / 3) + 1
    return `${year}Q${quarter}`
  }

  // カスタムツールチップ
  const CustomTooltip = ({
    active,
    payload,
    label,
  }: {
    active?: boolean
    payload?: Array<{
      name: string
      value: number | null
      color: string
      dataKey: string
    }>
    label?: string
  }) => {
    if (!active || !payload || payload.length === 0) return null

    return (
      <div
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          border: '1px solid #ddd',
          borderRadius: 8,
          padding: '12px 16px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        }}
      >
        <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14 }}>
          {formatQuarterLabel(label || '')}
        </div>
        {payload.map((item, index) => {
          const seriesName = item.dataKey === 'nominalGDP' ? '名目潜在成長率' : '実質潜在成長率'
          return (
            <div
              key={index}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 4,
                fontSize: 13,
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', marginRight: 16 }}>
                <span
                  style={{
                    display: 'inline-block',
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    backgroundColor: item.color,
                    marginRight: 6,
                  }}
                />
                {seriesName}
              </span>
              <span style={{ fontWeight: 500 }}>
                {formatPercentage(item.value)}
              </span>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div id="potential-gdp-chart">
      <ChartContainer
        title="名目潜在成長率 / 実質潜在成長率"
        showPeriodSelector={false}
        dataSource="FRED (CBO)"
      >
        {/* 最新値表示 */}
        <div
          style={{
            display: 'flex',
            gap: 16,
            marginBottom: 12,
            padding: '12px 16px',
            background: '#f5f5f5',
            borderRadius: 8,
          }}
        >
          {/* 実質潜在成長率 */}
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
              実質潜在成長率
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span
                style={{
                  fontSize: 20,
                  fontWeight: 'bold',
                  color: '#1890ff',
                }}
              >
                {latestReal ? formatPercentage(latestReal.value) : '-'}
              </span>
              {latestReal && (
                <span style={{ fontSize: 11, color: '#999' }}>
                  ({formatQuarterLabel(latestReal.date)})
                </span>
              )}
            </div>
          </div>

          {/* 名目潜在成長率 */}
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
              名目潜在成長率
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span
                style={{
                  fontSize: 20,
                  fontWeight: 'bold',
                  color: '#52c41a',
                }}
              >
                {latestNominal ? formatPercentage(latestNominal.value) : '-'}
              </span>
              {latestNominal && (
                <span style={{ fontSize: 11, color: '#999' }}>
                  ({formatQuarterLabel(latestNominal.date)})
                </span>
              )}
            </div>
          </div>
        </div>

        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

        <ZoomableChart
          data={filteredData}
          dataKey="realGDP"
          color="#1890ff"
          name="実質潜在成長率"
          height={450}
          tickFormatter={(v) => `${v.toFixed(1)}%`}
          xAxisTickFormatter={formatQuarterLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={false}
          showDefaultTooltip={false}
          additionalLines={[
            {
              dataKey: 'nominalGDP',
              color: '#52c41a',
              name: '名目潜在成長率',
              strokeWidth: 2,
            },
          ]}
        >
          <Tooltip content={<CustomTooltip />} />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
