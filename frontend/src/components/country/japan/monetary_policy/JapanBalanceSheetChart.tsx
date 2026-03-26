/**
 * 日銀バランスシート（総資産）チャートコンポーネント
 *
 * Bank of Japan Total Assets (JPNASSETS)
 * 月次データ（FRED経由）
 *
 * データソース:
 * - Bank of Japan via FRED (Federal Reserve Bank of St. Louis)
 *
 * 単位:
 * - 生データ: 億円
 * - 表示: 兆円
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
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../../usa/common/ChartComponents'
import { CHART_COLORS, DARK_THEME } from '../../usa/common/chartConstants'

// 型定義
import type { JapanBalanceSheetData } from '../../../../hooks/useDashboardData'

interface JapanBalanceSheetChartProps {
  data: JapanBalanceSheetData | null
}

interface JapanBalanceSheetChartData {
  date: string
  value: number // 億円
  value_trillion: number // 兆円
  [key: string]: string | number | null | undefined
}

export default function JapanBalanceSheetChart({ data }: JapanBalanceSheetChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)

  // propsのデータをチャート用に変換
  const chartData = useMemo<JapanBalanceSheetChartData[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const result: JapanBalanceSheetChartData[] = data.data.map((item) => ({
      date: item.date,
      value: item.value,
      value_trillion: item.value_trillion,
    }))

    // 日付でソート（古い順）
    result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return result
  }, [data])

  // 値フォーマット（兆円表記）
  const formatValue = (value: number) => {
    // value_trillionを使用（すでに兆円単位）
    return `¥${value.toFixed(1)}兆`
  }

  // Y軸フォーマット（兆円表記、簡略版）
  const formatYAxis = (value: number) => {
    // value（億円）を兆円に変換
    const trillions = value / 10000
    return `${trillions.toFixed(0)}兆`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2000,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="日銀バランスシート（総資産）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="日銀バランスシート（総資産）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="japan-balance-sheet-chart">
      <ChartContainer
        title="日銀バランスシート（総資産）"
        showPeriodSelector={false}
        dataSource="Bank of Japan (via FRED)"
        sourceUrl="https://fred.stlouisfed.org/series/JPNASSETS"
        handbookId="central-bank-balance-sheet"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="総資産残高"
          value={latestValue ? formatValue(latestValue.value_trillion) : null}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data?.next_release ? {
            date: data.next_release.date,
            label: data.next_release.label || `${data.next_release.time || '10:00'} JST`
          } : null}
          format="raw"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=japan_balance_sheet&s=boj_policy_rate', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLORS.primary}
          name="日銀総資産"
          height={450}
          tickFormatter={formatYAxis}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
          showDefaultTooltip={false}
          domain={['dataMin - 100000', 'dataMax + 100000']}
        >
          <RechartsTooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null
              const item = payload[0]
              // value（億円）を兆円に変換して表示
              const trillionValue = (item.value as number) / 10000
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
                    {formatDateLabel(String(label))}
                  </div>
                  <div
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
                          backgroundColor: CHART_COLORS.primary,
                          marginRight: 6,
                        }}
                      />
                      日銀総資産
                    </span>
                    <span style={{ fontWeight: 500, color: CHART_COLORS.primary }}>
                      ¥{trillionValue.toFixed(1)}兆
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
