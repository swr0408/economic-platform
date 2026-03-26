/**
 * 日本経常収支対GDP比チャートコンポーネント
 *
 * 経常収支対GDP比（Current Account to GDP Ratio）の推移を表示
 *
 * データソース:
 * - 経常収支: 財務省国際収支統計
 * - 名目GDP: 内閣府GDP統計
 *
 * 単位:
 * - 比率: %（percentage）
 *
 * 頻度:
 * - 四半期（Quarterly）
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip, ReferenceLine, XAxis, YAxis, CartesianGrid, ResponsiveContainer, ComposedChart, Area } from 'recharts'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  formatQuarterLabel,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
} from '../../usa/common/ChartComponents'
import { DARK_THEME, CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { JapanCurrentAccountGdpRatioData } from '../../../../hooks/useDashboardData'

interface JapanCurrentAccountGdpRatioChartProps {
  data: JapanCurrentAccountGdpRatioData | null
}

interface ChartDataItem {
  date: string
  value: number
  ratio: number
  current_account?: number
  nominal_gdp?: number
  [key: string]: string | number | boolean | null | undefined
}

export default function JapanCurrentAccountGdpRatioChart({ data }: JapanCurrentAccountGdpRatioChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(20)

  // 四半期形式（YYYY-QN）を日付形式（YYYY-MM-DD）に変換
  // Q1 → 01-01, Q2 → 04-01, Q3 → 07-01, Q4 → 10-01
  const quarterToDate = (quarterStr: string): string => {
    const match = quarterStr.match(/^(\d{4})-Q([1-4])$/)
    if (!match) return quarterStr
    const year = match[1]
    const quarter = parseInt(match[2], 10)
    const month = ((quarter - 1) * 3 + 1).toString().padStart(2, '0')
    return `${year}-${month}-01`
  }

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: ChartDataItem[] = data.data.map((item) => ({
      date: quarterToDate(item.date),  // YYYY-QN → YYYY-MM-DD に変換
      value: item.ratio,
      ratio: item.ratio,
      current_account: item.current_account,
      nominal_gdp: item.nominal_gdp,
    }))

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data])

  // 値フォーマット
  const formatPercent = (value: number) => {
    return `${value.toFixed(1)}%`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2000,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="経常収支対GDP比" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="経常収支対GDP比" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="japan-current-account-gdp-ratio-chart">
      <ChartContainer
        title="経常収支対GDP比"
        showPeriodSelector={false}
        dataSource="財務省 / 内閣府"
        sourceUrl="https://www.mof.go.jp/policy/international_policy/reference/balance_of_payments/"
        handbookId="current-account"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="経常収支対GDP比"
          value={latestValue?.ratio}
          valueColor={latestValue && latestValue.ratio < 0 ? CHART_COLORS.negative : CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data.next_release?.date ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="number"
          decimals={2}
          unit="%"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=japan_current_account_gdp_ratio', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart
            data={filteredData}
            margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
          >
            <defs>
              <linearGradient id="colorRatio" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={CHART_COLORS.primary} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={CHART_COLORS.primary} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.borderLight} />
            <XAxis
              dataKey="date"
              tickFormatter={formatQuarterLabel}
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              tickLine={{ stroke: DARK_THEME.borderLight }}
              axisLine={{ stroke: DARK_THEME.borderLight }}
            />
            <YAxis
              tickFormatter={formatPercent}
              tick={{ fill: DARK_THEME.textSecondary, fontSize: 11 }}
              tickLine={{ stroke: DARK_THEME.borderLight }}
              axisLine={{ stroke: DARK_THEME.borderLight }}
              domain={['dataMin - 0.5', 'dataMax + 0.5']}
            />
            <ReferenceLine y={0} stroke={DARK_THEME.textTertiary} strokeWidth={1} />
            <Area
              type="monotone"
              dataKey="ratio"
              name="経常収支対GDP比"
              stroke={CHART_COLORS.primary}
              strokeWidth={2}
              fill="url(#colorRatio)"
            />
            <RechartsTooltip
              content={({ active, payload, label }) => {
                if (!active || !payload || payload.length === 0) return null
                const dataItem = payload[0]?.payload as ChartDataItem
                const ratio = dataItem.ratio ?? 0
                const isNegative = ratio < 0
                return (
                  <div
                    style={{
                      backgroundColor: DARK_THEME.bgTertiary,
                      border: `1px solid ${DARK_THEME.borderLight}`,
                      borderRadius: 8,
                      padding: '12px 16px',
                      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                    }}
                  >
                    <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
                      {formatQuarterLabel(String(label))}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: '#f1f5f9', marginRight: 16 }}>
                          <span
                            style={{
                              display: 'inline-block',
                              width: 10,
                              height: 10,
                              borderRadius: 2,
                              backgroundColor: isNegative ? CHART_COLORS.negative : CHART_COLORS.primary,
                              marginRight: 6,
                            }}
                          />
                          経常収支対GDP比
                        </span>
                        <span style={{ fontWeight: 500, color: isNegative ? CHART_COLORS.negative : CHART_COLORS.primary }}>
                          {ratio.toFixed(2)}%
                        </span>
                      </div>
                      {dataItem.current_account !== undefined && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: DARK_THEME.textSecondary }}>
                          <span>経常収支</span>
                          <span>{((dataItem.current_account || 0) / 10000).toFixed(2)}兆円</span>
                        </div>
                      )}
                      {dataItem.nominal_gdp !== undefined && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: DARK_THEME.textSecondary }}>
                          <span>名目GDP</span>
                          <span>{((dataItem.nominal_gdp || 0) / 10000).toFixed(1)}兆円</span>
                        </div>
                      )}
                    </div>
                  </div>
                )
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
