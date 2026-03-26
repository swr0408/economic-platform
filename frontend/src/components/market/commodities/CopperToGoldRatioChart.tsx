import { useState, useMemo } from 'react'
import { Typography, Tooltip, Button } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import ChartContainer from '../../common/ChartContainer'
import LoadingChart from '../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatDayLabel } from '../../../utils/dateFormatters'
import { useHiddenSeries, usePeriodFiltering } from '../../country/usa/common/useChartData'
import { LATEST_VALUE_BOX_STYLE, CHART_MARGIN, DARK_THEME, TEXT_COLORS } from '../../country/usa/common/chartConstants'

const { Text } = Typography

const COLOR_RATIO = '#f59e0b'  // amber
const COLOR_COPPER = '#ef4444'  // red (薄表示)
const COLOR_GOLD = '#eab308'  // yellow (薄表示)

interface CopperToGoldRatioItem {
  date: string
  value: number
  copper: number
  gold: number
}

interface CopperToGoldRatioResponse {
  data: CopperToGoldRatioItem[]
  latest: CopperToGoldRatioItem | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useCopperToGoldRatioData() {
  return useQuery({
    queryKey: ['market', 'copper-to-gold-ratio'],
    queryFn: async () => {
      const { data } = await axios.get<CopperToGoldRatioResponse>('/api/market/copper-to-gold-ratio')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

export default function CopperToGoldRatioChart() {
  const { data: response, isLoading } = useCopperToGoldRatioData()
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const chartData = useMemo(() => {
    if (!response?.data) return []
    return [...response.data].sort((a, b) => a.date.localeCompare(b.date))
  }, [response])

  if (isLoading || !response) {
    return <LoadingChart title="銅金レシオ (Copper/Gold)" />
  }

  if (!chartData.length) {
    return (
      <ChartContainer title="銅金レシオ (Copper/Gold)" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: 40, color: TEXT_COLORS.secondary }}>データが利用できません</div>
      </ChartContainer>
    )
  }

  const latest = response.latest

  return (
    <div id="copper-to-gold-ratio">
      <ChartContainer
        title="銅金レシオ (Copper/Gold)"
        showPeriodSelector={false}
        dataSource="yfinance"
        handbookId="copper-to-gold-ratio"
      >
        {/* 最新値 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {latest && (
              <>
                <Text style={{ color: TEXT_COLORS.secondary, fontSize: 12 }}>{latest.date}</Text>
                <Text style={{ color: COLOR_RATIO, fontSize: 18, fontWeight: 700 }}>
                  {latest.value.toFixed(2)}
                </Text>
                <Text style={{ color: TEXT_COLORS.secondary, fontSize: 12 }}>
                  銅 ${latest.copper.toFixed(2)} / 金 ${latest.gold.toFixed(2)}
                </Text>
              </>
            )}
          </div>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=copper_to_gold_ratio', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート */}
        <CopperToGoldRatioInnerChart
          data={chartData}
          hiddenSeries={hiddenSeries}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}

function CopperToGoldRatioInnerChart({
  data,
  hiddenSeries,
  onLegendClick,
}: {
  data: CopperToGoldRatioItem[]
  hiddenSeries: Set<string>
  onLegendClick: (dataKey: string) => void
}) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  const filteredData = usePeriodFiltering(data, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  return (
    <>
      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
      <ResponsiveContainer width="100%" height={450}>
        <ComposedChart data={filteredData} margin={CHART_MARGIN}>
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.bgTertiary} />
          <XAxis
            dataKey="date"
            tickFormatter={formatDayLabel}
            stroke={DARK_THEME.textTertiary}
            tick={{ fill: DARK_THEME.textTertiary, fontSize: 10 }}
            minTickGap={40}
          />
          {/* 左Y軸: レシオ */}
          <YAxis
            yAxisId="left"
            domain={['dataMin * 0.95', 'dataMax * 1.05']}
            tickFormatter={(v: number) => v.toFixed(1)}
            stroke={DARK_THEME.textTertiary}
            tick={{ fill: DARK_THEME.textTertiary, fontSize: 10 }}
            width={50}
          />
          {/* 右Y軸: 銅 */}
          <YAxis
            yAxisId="copper"
            orientation="right"
            domain={['dataMin * 0.9', 'dataMax * 1.1']}
            tickFormatter={(v: number) => `$${v.toFixed(1)}`}
            stroke={COLOR_COPPER}
            tick={{ fill: COLOR_COPPER, fontSize: 10 }}
            width={55}
            axisLine={{ stroke: COLOR_COPPER, strokeDasharray: '4 3' }}
          />
          {/* 金の独立スケール軸（非表示） */}
          <YAxis
            yAxisId="gold"
            hide
            domain={['dataMin * 0.8', 'dataMax * 1.2']}
          />
          <RechartsTooltip
            contentStyle={{
              background: DARK_THEME.bgTertiary,
              border: `1px solid ${DARK_THEME.bgElevated}`,
              borderRadius: 6,
              fontSize: 12,
            }}
            labelStyle={{ color: DARK_THEME.textPrimary }}
            itemStyle={{ padding: '2px 0' }}
            formatter={(value: number, name: string) => {
              if (name.includes('レシオ')) return [value.toFixed(2), name]
              return [`$${value.toFixed(2)}`, name]
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, cursor: 'pointer' }}
            onClick={(e) => onLegendClick(e.dataKey as string)}
          />
          {/* レシオ（メイン線） */}
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="value"
            name="銅金レシオ"
            stroke={COLOR_RATIO}
            strokeWidth={2}
            dot={false}
            connectNulls
            hide={hiddenSeries.has('value')}
            isAnimationActive={false}
          />
          {/* 銅（右Y軸） */}
          <Line
            yAxisId="copper"
            type="monotone"
            dataKey="copper"
            name="銅 (USD, R)"
            stroke={COLOR_COPPER}
            strokeWidth={1}
            strokeOpacity={0.4}
            dot={false}
            connectNulls
            hide={hiddenSeries.has('copper')}
            isAnimationActive={false}
          />
          {/* 金（隠し軸） */}
          <Line
            yAxisId="gold"
            type="monotone"
            dataKey="gold"
            name="金 (USD)"
            stroke={COLOR_GOLD}
            strokeWidth={1}
            strokeOpacity={0.3}
            dot={false}
            connectNulls
            hide={hiddenSeries.has('gold')}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </>
  )
}
