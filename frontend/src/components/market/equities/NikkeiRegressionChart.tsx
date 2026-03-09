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
import PeriodSelector, { type PeriodValue } from '../../common/PeriodSelector'
import { formatMonthLabel, formatDayLabel } from '../../../utils/dateFormatters'

const { Text } = Typography

const DARK_THEME = {
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  bgTertiary: '#334155',
  gridLine: '#475569',
  axisLine: '#64748b',
  tooltipBg: '#334155',
  tooltipBorder: '#475569',
  chartBg: '#1e293b',
}

const ACTUAL_COLOR = '#3b82f6'
const MODEL_COLOR = '#ef4444'

interface NikkeiRegressionItem {
  date: string
  actual: number | null
  model: number | null
}

interface ModelInfo {
  coef_afre_12ma: number
  coef_usdjpy: number
  intercept: number
  r_squared: number
  train_period: string
  train_samples: number
}

interface NikkeiRegressionResponse {
  data: NikkeiRegressionItem[]
  latest: NikkeiRegressionItem | null
  model_info: ModelInfo | null
  metadata: Record<string, unknown>
  cached: boolean
  source: string
  last_updated: string | null
}

function useNikkeiRegressionData() {
  return useQuery({
    queryKey: ['market', 'nikkei-regression'],
    queryFn: async () => {
      const { data } = await axios.get<NikkeiRegressionResponse>('/api/market/nikkei-regression')
      return data
    },
    staleTime: 60 * 60 * 1000,
    refetchOnMount: false,
  })
}

function CustomTooltip({ active, payload, label }: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  const formattedLabel = formatDayLabel(String(label))
  const actualItem = payload.find((p: { dataKey: string }) => p.dataKey === 'actual')
  const modelItem = payload.find((p: { dataKey: string }) => p.dataKey === 'model')

  return (
    <div
      style={{
        backgroundColor: DARK_THEME.tooltipBg,
        border: `1px solid ${DARK_THEME.tooltipBorder}`,
        borderRadius: 8,
        padding: '12px 16px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
      }}
    >
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: '#f1f5f9' }}>
        {formattedLabel}
      </div>

      {actualItem && typeof actualItem.value === 'number' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: ACTUAL_COLOR, marginRight: 6 }} />
            日経平均
          </span>
          <span style={{ fontWeight: 500, color: ACTUAL_COLOR }}>
            {actualItem.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </div>
      )}

      {modelItem && typeof modelItem.value === 'number' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
          <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, backgroundColor: MODEL_COLOR, marginRight: 6 }} />
            モデル値
          </span>
          <span style={{ fontWeight: 500, color: MODEL_COLOR }}>
            {modelItem.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        </div>
      )}

      {actualItem && modelItem && typeof actualItem.value === 'number' && typeof modelItem.value === 'number' && (
        <div style={{ fontSize: 11, color: DARK_THEME.textSecondary, marginTop: 4, borderTop: '1px solid #475569', paddingTop: 4 }}>
          乖離: {((actualItem.value - modelItem.value) / modelItem.value * 100).toFixed(1)}%
        </div>
      )}
    </div>
  )
}

export default function NikkeiRegressionChart() {
  const { data: apiData, isLoading } = useNikkeiRegressionData()
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodValue>(20)

  const chartData = useMemo(() => {
    if (!apiData?.data) return []
    return apiData.data
      .map((d) => ({
        date: d.date,
        actual: d.actual,
        model: d.model,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [apiData])

  const filteredData = useMemo(() => {
    if (selectedPeriod === 'all') return chartData
    if (selectedPeriod === 'default') {
      const cutoff = new Date()
      cutoff.setFullYear(cutoff.getFullYear() - 5)
      const cutoffStr = cutoff.toISOString().slice(0, 10)
      return chartData.filter((d) => d.date >= cutoffStr)
    }
    const years = typeof selectedPeriod === 'number' ? selectedPeriod : 5
    const cutoff = new Date()
    cutoff.setFullYear(cutoff.getFullYear() - years)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return chartData.filter((d) => d.date >= cutoffStr)
  }, [chartData, selectedPeriod])

  if (isLoading) {
    return (
      <ChartContainer title="日経平均株価回帰モデル" loading showPeriodSelector={false}>
        <div />
      </ChartContainer>
    )
  }

  if (!apiData || chartData.length === 0) {
    return (
      <ChartContainer title="日経平均株価回帰モデル" showPeriodSelector={false}>
        <div style={{ textAlign: 'center', padding: 40, color: DARK_THEME.textSecondary }}>
          データがありません
        </div>
      </ChartContainer>
    )
  }

  const latest = apiData.latest

  return (
    <ChartContainer
      title="日経平均株価回帰モデル"
      dataSource="PBOC / yfinance"
      sourceUrl="https://camlmac.pbc.gov.cn/diaochatongjisi/116219/116319/index.html"
      showPeriodSelector={false}
    >
      {/* 最新値 + モデル情報 */}
      {latest && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            marginBottom: 12,
            padding: '10px 14px',
            background: DARK_THEME.bgTertiary,
            borderRadius: 8,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>実績</Text>
            <Text
              style={{ color: ACTUAL_COLOR, fontSize: 18, fontWeight: 700 }}
              className="tabular-nums"
            >
              {latest.actual != null ? latest.actual.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '—'}
            </Text>
          </div>

          {latest.model != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>モデル</Text>
              <Text
                style={{ color: MODEL_COLOR, fontSize: 18, fontWeight: 700 }}
                className="tabular-nums"
              >
                {latest.model.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </Text>
            </div>
          )}

          {latest.actual != null && latest.model != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <Text style={{ color: DARK_THEME.textSecondary, fontSize: 12 }}>乖離</Text>
              <Text
                style={{
                  color: latest.actual > latest.model ? '#22c55e' : '#ef4444',
                  fontSize: 14,
                  fontWeight: 600,
                }}
                className="tabular-nums"
              >
                {((latest.actual - latest.model) / latest.model * 100).toFixed(1)}%
              </Text>
            </div>
          )}

          <Text style={{ color: DARK_THEME.textSecondary, fontSize: 11 }}>
            ({latest.date})
          </Text>
        </div>
      )}

      {/* モデル情報 */}
      {/* {modelInfo && (
        <div style={{
          fontSize: 11,
          color: DARK_THEME.textSecondary,
          marginBottom: 8,
          padding: '6px 10px',
          background: 'rgba(51,65,85,0.5)',
          borderRadius: 4,
        }}>
          <span>Nikkei = {modelInfo.coef_afre_12ma.toFixed(2)} × AFRE_12MA + {modelInfo.coef_usdjpy.toFixed(2)} × USDJPY + ({modelInfo.intercept.toFixed(0)})</span>
          <span style={{ marginLeft: 12 }}>R² = {modelInfo.r_squared.toFixed(3)}</span>
          <span style={{ marginLeft: 12 }}>学習: {modelInfo.train_period} ({modelInfo.train_samples}pts)</span>
        </div>
      )} */}

      {/* データ比較ボタン */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            size="small"
            onClick={() => window.open('/compare?s=nikkei_regression_model', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* 期間選択 */}
      <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

      {/* チャート */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart
          data={filteredData}
          margin={{ top: 16, right: 8, bottom: 0, left: 0 }}
          style={{ backgroundColor: DARK_THEME.chartBg }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.gridLine} fill={DARK_THEME.chartBg} />

          <XAxis
            type="category"
            dataKey="date"
            tickFormatter={formatMonthLabel}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={16}
            height={60}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={['dataMin - 2000', 'dataMax + 2000']}
            tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`}
            axisLine={{ stroke: DARK_THEME.axisLine }}
            tickLine={{ stroke: DARK_THEME.axisLine }}
            tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
            tickMargin={8}
          />

          <RechartsTooltip content={<CustomTooltip />} />

          <Legend wrapperStyle={{ paddingTop: 8 }} />

          <Line
            type="monotone"
            dataKey="actual"
            stroke={ACTUAL_COLOR}
            strokeWidth={1.5}
            dot={false}
            name="日経平均株価"
            connectNulls
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="model"
            stroke={MODEL_COLOR}
            strokeWidth={2}
            dot={false}
            name="回帰モデル"
            strokeDasharray="6 3"
            connectNulls
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
