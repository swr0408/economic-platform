/**
 * UK QT（量的引締め）チャートコンポーネント
 *
 * APF（Asset Purchase Facility）ギルト保有残高の推移を表示
 *
 * データソース:
 * - Bank of England Statistical Interactive Database (IADB)
 * - Series: YWWB9T9
 *
 * 発表スケジュール:
 * - 週次（毎週木曜 15:00 London時間）
 *
 * 単位:
 * - GBP billions（十億ポンド）
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
import type { UKQTData } from '../../../../hooks/useDashboardData'

interface UkQtChartProps {
  data: UKQTData | null
}

interface UkQtChartData {
  date: string
  value: number // GBP billions
  [key: string]: string | number | null | undefined
}

export default function UkQtChart({ data }: UkQtChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(20)

  // propsのデータをチャート用に変換
  const chartData = useMemo<UkQtChartData[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const result: UkQtChartData[] = data.data.map((item) => ({
      date: item.date,
      value: item.value,
    }))

    // 日付でソート（古い順）
    result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return result
  }, [data])

  // 値フォーマット（£Xbn）
  const formatValue = (value: number) => {
    return `£${value.toFixed(0)}bn`
  }

  // Y軸フォーマット
  const formatYAxis = (value: number) => {
    return `${value.toFixed(0)}`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2009,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="APFギルト保有残高" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="APFギルト保有残高" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="uk-qt-chart">
      <ChartContainer
        title="APFギルト保有残高（QT）"
        showPeriodSelector={false}
        dataSource="Bank of England"
        sourceUrl="https://www.bankofengland.co.uk/boeapps/database/"
        handbookId="uk-qt"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="APFギルト保有残高"
          value={latestValue ? formatValue(latestValue.value) : null}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data?.next_release ? {
            date: data.next_release.date,
            time_jst: data.next_release.time_jst,
          } : undefined}
          format="raw"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=uk_qt', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color={CHART_COLORS.primary}
          name="APFギルト保有残高"
          height={450}
          tickFormatter={formatYAxis}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
          showDefaultTooltip={false}
          domain={['dataMin - 10', 'dataMax + 10']}
        >
          <RechartsTooltip
            content={({ active, payload, label }) => {
              if (!active || !payload || payload.length === 0) return null
              const item = payload[0]
              const value = item.value as number
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
                      APFギルト保有残高
                    </span>
                    <span style={{ fontWeight: 500, color: CHART_COLORS.primary }}>
                      £{value.toFixed(1)}bn
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
