/**
 * ON RRP（Overnight Reverse Repo）チャートコンポーネント
 *
 * NY Fed Markets API から取得した RRP オペ残高を表示
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../common/ChartComponents'
import { CHART_COLORS, DARK_THEME } from '../common/chartConstants'
import type { ONRRPData, ONRRPItem } from '../../../../hooks/useDashboardData'

// Props型定義
interface ONRRPChartProps {
  data: ONRRPData | null
}

interface ChartDataItem {
  date: string
  value: number | null
  [key: string]: string | number | null | undefined
}

export default function ONRRPChart({ data }: ONRRPChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(2)

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data || !data.data || data.data.length === 0) return []

    const result: ChartDataItem[] = data.data.map((item: ONRRPItem) => ({
      date: item.date,
      value: item.value,
    }))

    // 日付でソート（古い順）
    result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return result
  }, [data])

  // 値フォーマット（十億ドル単位）
  const formatValue = (value: number) => {
    return `$${value.toFixed(1)}B`
  }

  // Y軸フォーマット
  const formatYAxis = (value: number) => {
    return `${value.toFixed(0)}B`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2021,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="ON RRP（Overnight Reverse Repo）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ON RRP（Overnight Reverse Repo）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="on-rrp-chart">
      <ChartContainer
        title="ON RRP（Overnight Reverse Repo）"
        showPeriodSelector={false}
        dataSource="NY Fed"
        sourceUrl="https://www.newyorkfed.org/markets/desk-operations/reverse-repo"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="ON RRP残高"
          value={latestValue?.value != null ? formatValue(latestValue.value) : null}
          valueColor={CHART_COLORS.cyan}
          date={latestValue?.date}
          format="raw"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=on_rrp&s=tga&s=reserve_balances', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLORS.cyan}
          name="ON RRP"
          height={450}
          tickFormatter={formatYAxis}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
          showDefaultTooltip={false}
          domain={[0, 'auto']}
        >
          <RechartsTooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null
              const dataPoint = payload[0]?.payload as ChartDataItem | undefined
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
                    {String(label).replace(/-/g, '/')}
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
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
                          backgroundColor: CHART_COLORS.cyan,
                          marginRight: 6,
                        }}
                      />
                      ON RRP
                    </span>
                    <span style={{ fontWeight: 500, color: CHART_COLORS.cyan }}>
                      {dataPoint?.value != null ? formatValue(dataPoint.value) : 'N/A'}
                    </span>
                  </div>
                </div>
              )
            }}
          />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
