import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS, CUSTOM_TOOLTIP_STYLE } from '../common/chartConstants'
import { usePeriodFiltering, formatQuarterLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage } from '../common/ChartComponents'

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
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')

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
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2000,
  })

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="名目潜在成長率 / 実質潜在成長率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="名目潜在成長率 / 実質潜在成長率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
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
      <div style={CUSTOM_TOOLTIP_STYLE}>
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
              <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
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
              <span style={{ fontWeight: 500, color: item.color }}>
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
        sourceUrl="https://www.cbo.gov/taxonomy/term/6/recurring-reports"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>最新値</span>
          {/* 名目潜在成長率 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>名目:</span>
            <span style={{ fontSize: 16, fontWeight: 'bold', color: '#52c41a' }}>
              {latestNominal ? formatPercentage(latestNominal.value) : '-'}
            </span>
            {latestNominal && (
              <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
                ({formatQuarterLabel(latestNominal.date)})
              </span>
            )}
          </div>
          {/* 実質潜在成長率 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>実質:</span>
            <span style={{ fontSize: 16, fontWeight: 'bold', color: '#1890ff' }}>
              {latestReal ? formatPercentage(latestReal.value) : '-'}
            </span>
            {latestReal && (
              <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
                ({formatQuarterLabel(latestReal.date)})
              </span>
            )}
          </div>
        </div>

        {/* 期間セレクタ + 比較ボタン（横並び） */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=potential_gdp_real', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート */}
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
          <RechartsTooltip content={<CustomTooltip />} />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
