/**
 * カナダ決済残高（Settlement Balances）チャートコンポーネント
 *
 * Lynx Settlement Balances の推移を表示
 * - 日次データ: ACTUAL（Lynx決済残高の実績値）
 * - 週次データ: V36636（Members of Payments Canada deposits）
 * - 短期資金市場の流動性指標
 * - CORRAのタイト/ルーズを判断する指標
 *
 * データソース:
 * - Bank of Canada Valet API
 *
 * 発表スケジュール:
 * - 日次: 営業日ベース
 * - 週次: 金曜 14:30 ET
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Button, Tooltip, Radio } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, formatDateLabelFull, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'

// 型定義
import type { CaSettlementBalancesData } from '../../../../hooks/useDashboardData'

interface CaSettlementBalancesChartProps {
  data: CaSettlementBalancesData | null
}

interface ChartDataItem {
  date: string
  value: number
  [key: string]: string | number | null | undefined
}

type ViewMode = 'daily' | 'weekly'

export default function CaSettlementBalancesChart({ data }: CaSettlementBalancesChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [viewMode, setViewMode] = useState<ViewMode>('daily')

  // 選択されたビューモードに応じたデータを取得
  const selectedData = useMemo(() => {
    if (!data) return null
    if (viewMode === 'daily') {
      return data.daily
    } else {
      return data.weekly
    }
  }, [data, viewMode])

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!selectedData?.data || selectedData.data.length === 0) return []

    const formattedData: ChartDataItem[] = selectedData.data.map((item) => ({
      date: item.date,
      value: item.value,
    }))

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [selectedData])

  const formatValue = (value: number) => {
    // 百万CAD単位で表示
    return `${(value / 1000).toFixed(1)}B`
  }

  const formatTooltipValue = (value: number) => {
    // ツールチップでは詳細に表示
    return `${value.toLocaleString()} M CAD`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: viewMode === 'daily' ? 2020 : 2020,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = selectedData?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="決済残高（Settlement Balances）" />
  }

  // 日次データと週次データの両方が空の場合
  const hasDailyData = data.daily?.data && data.daily.data.length > 0
  const hasWeeklyData = data.weekly?.data && data.weekly.data.length > 0

  if (!hasDailyData && !hasWeeklyData) {
    return (
      <ChartContainer title="決済残高（Settlement Balances）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // チャート名とデータ比較URLを動的に設定
  const chartName = viewMode === 'daily' ? 'Lynx Settlement Balances（日次）' : 'Payments Canada Deposits（週次）'
  const compareUrl = viewMode === 'daily' ? '/compare?s=ca_settlement_balances_daily' : '/compare?s=ca_settlement_balances_weekly'

  return (
    <div id="ca-settlement-balances-chart">
      <ChartContainer
        title="決済残高（Settlement Balances）"
        showPeriodSelector={false}
        dataSource="Bank of Canada"
        sourceUrl="https://www.bankofcanada.ca/rates/indicators/market-operations-indicators/"
      >
        {/* ViewMode切り替え */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <Radio.Group
            value={viewMode}
            onChange={(e) => setViewMode(e.target.value)}
            buttonStyle="solid"
            size="small"
          >
            <Radio.Button value="daily" disabled={!hasDailyData}>
              日次（ACTUAL）
            </Radio.Button>
            <Radio.Button value="weekly" disabled={!hasWeeklyData}>
              週次（V36636）
            </Radio.Button>
          </Radio.Group>
          <span style={{ fontSize: 12, color: DARK_THEME.textSecondary }}>
            {viewMode === 'daily' ? 'Lynx決済残高（営業日更新）' : 'Payments Canada deposits（金曜14:30 ET公表）'}
          </span>
        </div>

        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={viewMode === 'daily' ? '最新残高（日次）' : '最新残高（週次）'}
          value={latestValue?.value}
          valueColor="#3B82F6"
          date={latestValue?.date}
          format="number"
          decimals={0}
          unit="M CAD"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open(compareUrl, '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {hasData ? (
          <ZoomableChart
            data={filteredData}
            dataKey="value"
            color="#3B82F6"
            name={chartName}
            height={450}
            tickFormatter={formatValue}
            xAxisTickFormatter={formatDateLabel}
            enableDynamicTicks={true}
            showZeroLine={false}
            showFiftyLine={false}
            connectNulls={true}
            hideLegend={true}
            showDefaultTooltip={false}
            domain={['dataMin - 10000', 'dataMax + 10000']}
          >
            <RechartsTooltip
              content={({ active, payload, label }) => {
                if (!active || !payload || payload.length === 0) return null
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
                      {formatDateLabelFull(String(label))}
                    </div>
                    {payload.map((item, index) => (
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
                              backgroundColor: item.color || '#3B82F6',
                              marginRight: 6,
                            }}
                          />
                          {item.name}
                        </span>
                        <span style={{ fontWeight: 500, color: item.color || '#3B82F6' }}>
                          {formatTooltipValue(item.value as number)}
                        </span>
                      </div>
                    ))}
                  </div>
                )
              }}
            />
          </ZoomableChart>
        ) : (
          <NoDataMessage />
        )}
      </ChartContainer>
    </div>
  )
}
