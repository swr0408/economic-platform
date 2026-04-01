/**
 * ISM製造業受注在庫バランスチャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import { Tabs } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { ISMComponentsData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'
import {
  usePeriodFiltering,
  formatDateLabel,
  useHiddenSeries,
  createNumberFormatter,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface OrderInventoryBalanceChartProps {
  data: ISMComponentsData | null
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function OrderInventoryBalanceChart({ data }: OrderInventoryBalanceChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<string>(['balance'])

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        balance: item.order_inventory_balance,
        balance_3ma: item.order_inventory_balance_3ma,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="ISM製造業受注在庫バランス" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="ISM製造業受注在庫バランス" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const formatValue = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'N/A'
    return value.toFixed(1)
  }

  // 最新値を取得
  const latestData = data.latest
  const latestBalance = latestData?.order_inventory_balance
  const latestBalance3MA = latestData?.order_inventory_balance_3ma

  return (
    <div id="order-inventory-balance-chart">
      <ChartContainer
        title="ISM製造業受注在庫バランス"
        showPeriodSelector={false}
        dataSource="ISM"
        sourceUrl="https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/"
        handbookId="order-inventory-balance"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ flex: '0 0 auto' }}>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>最新: </span>
            {latestData && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary }}>
                ({formatDateLabel(latestData.date)})
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: 2,
                backgroundColor: '#228B22',
                display: 'inline-block',
              }}
            />
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>3ヶ月平均:</span>
            <span style={{ fontSize: 14, fontWeight: 'bold', color: '#228B22' }}>
              {formatValue(latestBalance3MA)}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: 2,
                backgroundColor: 'rgba(34, 139, 34, 0.5)',
                display: 'inline-block',
              }}
            />
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>当月:</span>
            <span style={{ fontSize: 14, fontWeight: 'bold', color: 'rgba(34, 139, 34, 0.8)' }}>
              {formatValue(latestBalance)}
            </span>
          </div>
        </div>

        {/* 次回発表日 */}
        {data.next_release && (
          <div
            style={{
              marginBottom: 12,
              padding: '8px 16px',
              background: '#fff7e6',
              borderRadius: 8,
              borderLeft: '4px solid #faad14',
            }}
          >
            <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>次回発表: </span>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{data.next_release.date}</span>
          </div>
        )}

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />

                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'balance_3ma', color: '#228B22', name: '受注在庫バランス（3ヶ月平均）', strokeWidth: 2, hide: hiddenSeries.has('balance_3ma') },
                      { dataKey: 'balance', color: 'rgba(141, 250, 141, 0.5)', name: '受注在庫バランス（当月）', strokeWidth: 1, hide: hiddenSeries.has('balance') },
                    ]}
                    yAxisFormatter={(v) => v.toFixed(0)}
                    yDomain={['dataMin - 2', 'dataMax + 2']}
                    tooltipLabelFormatter={formatDateLabel}
                    tooltipFormatter={createNumberFormatter(1)}
                    onLegendClick={handleLegendClick}
                    showZeroLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ism_manufacturing" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
