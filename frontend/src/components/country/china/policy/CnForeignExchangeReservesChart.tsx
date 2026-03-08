/**
 * 中国 外貨準備（Foreign Exchange Reserves）チャートコンポーネント
 *
 * ビューモード:
 * - 原数値:   外貨準備高（亿美元）折れ線
 * - 前年比:   前年比（%）折れ線
 *
 * データソース: 国家外汇管理局（SAFE）
 *
 * FMPマッピング:
 * - Foreign Exchange Reserves (econalpha_id: cn_foreign_exchange_reserves)
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CnForexReservesData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface CnForeignExchangeReservesChartProps {
  data: CnForexReservesData | null
}

type ViewMode = 'value' | 'yoy'
const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'value', label: '原数値' },
  { mode: 'yoy',   label: '前年比' },
]

const COLOR_VALUE = '#0ea5e9'  // スカイブルー
const COLOR_YOY   = '#f59e0b'  // オレンジ

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnForeignExchangeReservesChart({ data }: CnForeignExchangeReservesChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    value: 10,
    yoy:   10,
  })

  const sortedData = useSortedData(data?.data ?? [])

  const filteredBase = useMemo(() => {
    if (viewMode === 'value') return sortedData.filter(d => d.value != null)
    if (viewMode === 'yoy')   return sortedData.filter(d => d.yoy != null)
    return sortedData
  }, [sortedData, viewMode])

  const filteredData = usePeriodFiltering(filteredBase, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="外貨準備" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="外貨準備" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latestWithValue = [...sortedData].reverse().find(d => d.value != null)
  const latestWithYoy   = [...sortedData].reverse().find(d => d.yoy != null)

  const latestValue =
    viewMode === 'value' ? (latestWithValue?.value ?? null)
    : (latestWithYoy?.yoy ?? null)

  const latestDate =
    viewMode === 'value' ? latestWithValue?.date
    : latestWithYoy?.date

  const latestLabel =
    viewMode === 'value' ? '外貨準備高'
    : '外貨準備高（前年比）'

  const latestUnit =
    viewMode === 'value' ? '亿美元'
    : '%'

  const latestDecimals =
    viewMode === 'value' ? 2
    : 2

  const latestColor =
    viewMode === 'value' ? COLOR_VALUE
    : COLOR_YOY

  return (
    <div id="forex-reserves">
      <ChartContainer
        title="外貨準備"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="国家外汇管理局（SAFE）"
        sourceUrl="https://www.safe.gov.cn/en/ForexReserves/index.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={latestLabel}
          value={latestValue}
          date={latestDate}
          unit={latestUnit}
          decimals={latestDecimals}
          valueColor={latestColor}
          dateFormatter={formatDateFull}
          nextRelease={data.next_release ?? null}
        />

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
                  {/* ビューモード切替 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      options={VIEW_MODE_OPTIONS}
                      currentMode={viewMode}
                      onChange={setViewMode}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_foreign_exchange_reserves', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 期間選択 */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* 原数値: 折れ線 */}
                  {viewMode === 'value' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'value', color: COLOR_VALUE, name: '外貨準備高（亿美元）' },
                      ]}
                      yAxisFormatter={(v) => `${(v / 10000).toFixed(1)}万亿`}
                      yDomain={['dataMin - 500', 'dataMax + 500']}
                      xAxisFormatter={formatDateLabel}
                      tooltipLabelFormatter={formatDateFull}
                      tooltipValueFormatter={(v) => `${v.toLocaleString()} 亿美元`}
                      showZeroLine={false}
                      showLegend={false}
                    />
                  )}

                  {/* 前年比: 折れ線 */}
                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLOR_YOY, name: '前年比（%）' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
                      xAxisFormatter={formatDateLabel}
                      tooltipLabelFormatter={formatDateFull}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      showZeroLine={true}
                      showLegend={false}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="cn_foreign_exchange_reserves" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
