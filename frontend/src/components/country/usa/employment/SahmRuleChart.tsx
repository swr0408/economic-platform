/**
 * サームルールチャートコンポーネント
 *
 * FRED SAHMCURRENT シリーズを使用
 * - Sahm Rule Recession Indicator（サームルール景気後退指標）
 *
 * 月次データ（毎月第1金曜日発表、雇用統計と同時）
 *
 * サームルール:
 * - 失業率の3ヶ月移動平均が、過去12ヶ月の最低値から0.5%以上上昇すると景気後退シグナル
 * - 0.5%のラインが重要な閾値
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

// Props型定義
interface SahmRuleItem {
  date: string
  value: number
}

interface SahmRuleChartProps {
  data: SahmRuleItem[] | null
}

interface SahmRuleChartData {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

// サームルールの閾値
const SAHM_THRESHOLD = 0.5

export default function SahmRuleChart({ data }: SahmRuleChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)

  // propsのデータをチャート用に変換
  const chartData = useMemo<SahmRuleChartData[]>(() => {
    if (!data || data.length === 0) return []

    const result: SahmRuleChartData[] = data.map((item) => ({
      date: item.date,
      value: item.value,
    }))

    // 日付でソート（古い順）
    result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return result
  }, [data])

  // 値フォーマット
  const formatValue = (value: number) => {
    return `${value.toFixed(2)}%`
  }

  // Y軸フォーマット
  const formatYAxis = (value: number) => {
    return `${value.toFixed(1)}%`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2000,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null

  // 閾値との比較で色を決定（0.5%以上で景気後退シグナル = 赤）
  const valueColor = latestValue && latestValue.value >= SAHM_THRESHOLD
    ? CHART_COLORS.red
    : CHART_COLORS.green

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="サームルール（Sahm Rule）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="サームルール（Sahm Rule）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="sahm-rule-chart">
      <ChartContainer
        title="サームルール（Sahm Rule）"
        showPeriodSelector={false}
        dataSource="FRED"
        sourceUrl="https://fred.stlouisfed.org/series/SAHMCURRENT"
        handbookId="sahm-rule"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="Sahm Rule"
          value={latestValue ? formatValue(latestValue.value) : null}
          valueColor={valueColor}
          date={latestValue?.date}
          format="raw"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=sahm_rule', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLORS.primary}
          name="Sahm Rule"
          height={450}
          tickFormatter={formatYAxis}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
          showDefaultTooltip={false}
          domain={['dataMin - 0.1', 'dataMax + 0.1']}
        >
          <RechartsTooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null
              const value = payload[0].value as number
              // 閾値超え判定
              const isAboveThreshold = value >= SAHM_THRESHOLD
              const displayColor = isAboveThreshold ? CHART_COLORS.red : CHART_COLORS.green
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
                      Sahm Rule
                    </span>
                    <span style={{ fontWeight: 500, color: displayColor }}>
                      {formatValue(value)}
                    </span>
                  </div>
                  {isAboveThreshold && (
                    <div style={{ fontSize: 11, color: CHART_COLORS.red, marginTop: 4 }}>
                      ⚠️ 景気後退シグナル（0.5%超）
                    </div>
                  )}
                </div>
              )
            }}
          />
        </ZoomableChart>
      </ChartContainer>
    </div>
  )
}
