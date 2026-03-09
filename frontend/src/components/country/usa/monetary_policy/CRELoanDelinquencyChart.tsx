/**
 * CREローン延滞率（Commercial Real Estate Loan Delinquency Rate）チャートコンポーネント
 *
 * 3つのシリーズをボタンで切り替え:
 * - all_banks: 全商業銀行
 * - top_100: 資産規模上位100行
 * - other_banks: 上位100行以外
 *
 * データソース: FRB Charge-Off and Delinquency Rates
 * 四半期データ（2月・5月・8月・11月発表）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip, Radio } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage, StandardLineChart } from '../common/ChartComponents'
import { CHART_COLORS, DARK_THEME, LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import type { CRELoanDelinquencyData } from '../../../../hooks/useDashboardData'

// Props型定義
interface CRELoanDelinquencyChartProps {
  data: CRELoanDelinquencyData | null
}

interface ChartDataItem {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

type SeriesType = 'all_banks' | 'top_100' | 'other_banks'

const SERIES_CONFIG: Record<SeriesType, { label: string; name: string; color: string }> = {
  all_banks: {
    label: '全銀行',
    name: 'All Commercial Banks',
    color: CHART_COLORS.red,
  },
  top_100: {
    label: '上位100行',
    name: 'Top 100 Banks',
    color: CHART_COLORS.orange,
  },
  other_banks: {
    label: 'その他',
    name: 'Other Banks',
    color: CHART_COLORS.primary,
  },
}

export default function CRELoanDelinquencyChart({ data }: CRELoanDelinquencyChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(20)
  const [selectedSeries, setSelectedSeries] = useState<SeriesType>('all_banks')

  // 選択されたシリーズのデータを取得
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data || !data.data || data.data.length === 0) return []

    const result: ChartDataItem[] = data.data
      .filter((item) => item[selectedSeries] != null)
      .map((item) => ({
        date: item.date,
        value: item[selectedSeries] as number,
      }))

    // 日付でソート（古い順）
    result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return result
  }, [data, selectedSeries])

  // 値フォーマット
  const formatValue = (value: number) => {
    return `${value.toFixed(2)}%`
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
    return <LoadingChart title="CREローン延滞率（Commercial Real Estate Loan Delinquency）" />
  }

  if (!hasData) {
    return (
      <ChartContainer
        title="CREローン延滞率（Commercial Real Estate Loan Delinquency）"
        showPeriodSelector={false}
        showDataSource={false}
      >
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="cre-loan-delinquency-chart">
      <ChartContainer
        title="CREローン延滞率（Commercial Real Estate Loan Delinquency）"
        showPeriodSelector={false}
        dataSource="FRB (FRED)"
        sourceUrl="https://www.federalreserve.gov/releases/chargeoff/"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>
                最新値
              </span>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>全銀行:</span>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: CHART_COLORS.red }}>
                  {latestValue?.all_banks != null ? formatValue(latestValue.all_banks) : '-'}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>上位100行:</span>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: CHART_COLORS.orange }}>
                  {latestValue?.top_100 != null ? formatValue(latestValue.top_100) : '-'}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>その他:</span>
                <span style={{ fontSize: 16, fontWeight: 'bold', color: CHART_COLORS.primary }}>
                  {latestValue?.other_banks != null ? formatValue(latestValue.other_banks) : '-'}
                </span>
              </div>

              {latestValue?.date && (
                <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary }}>
                  ({formatDateLabel(latestValue.date)})
                </span>
              )}
            </div>

            {data?.next_release && (
              <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
                次回発表: {data.next_release.date}
              </div>
            )}
          </div>
        </div>

        {/* シリーズ切り替え */}
        <div style={{ marginBottom: 16 }}>
          <Radio.Group
            value={selectedSeries}
            onChange={(e) => setSelectedSeries(e.target.value)}
            buttonStyle="solid"
            size="middle"
          >
            <Radio.Button value="all_banks">全商業銀行(All Banks)</Radio.Button>
            <Radio.Button value="top_100">上位100行(Top 100)</Radio.Button>
            <Radio.Button value="other_banks">その他(Other Banks)</Radio.Button>
          </Radio.Group>
        </div>

        {/* 期間選択 + 比較ボタン */}
        <div
          style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}
        >
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="データ比較">
            <Button
              type="text"
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=cre_loan_delinquency_rate', '_blank')}
              style={{ color: DARK_THEME.textSecondary }}
            />
          </Tooltip>
        </div>

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: 'value',
              color: SERIES_CONFIG[selectedSeries].color,
              name: SERIES_CONFIG[selectedSeries].name,
            },
          ]}
          yAxisFormatter={(v) => `${v.toFixed(1)}%`}
          tooltipValueFormatter={(v) => `${Number(v).toFixed(2)}%`}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
