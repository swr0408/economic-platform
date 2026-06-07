/**
 * 中国 資本フロー（Capital Flows）チャートコンポーネント
 *
 * SAFE（国家外汇管理局）银行代客涉外收付款数据
 * 三、收支差额（Net Balance）セクションの7系列を表示
 *
 * 2ビュー構成:
 * 1. 総合（overview）: net_total / net_current / net_capital
 * 2. 詳細（detail）: net_goods / net_services / net_securities / net_other
 *
 * データソース: SAFE https://www.safe.gov.cn/safe/2018/0419/8806.html
 * FMPマッピング: なし
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

import type { CnCapitalFlowsData, CnCapitalFlowsItem } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnCapitalFlowsData | null
}

type ViewMode = 'overview' | 'detail'

type OverviewKey = 'net_total' | 'net_current' | 'net_capital'
type DetailKey = 'net_goods' | 'net_services' | 'net_securities' | 'net_other'
type SeriesKey = OverviewKey | DetailKey

const VIEW_MODE_OPTIONS = [
  { mode: 'overview' as ViewMode, label: '総合' },
  { mode: 'detail' as ViewMode, label: '詳細' },
]

const OVERVIEW_SERIES: { key: OverviewKey; label: string; color: string }[] = [
  { key: 'net_total',   label: '収支差額',     color: '#ef4444' },  // 赤
  { key: 'net_current', label: '経常勘定',     color: '#3b82f6' },  // 青
  { key: 'net_capital', label: '資本・金融勘定', color: '#f97316' },  // オレンジ
]

const DETAIL_SERIES: { key: DetailKey; label: string; color: string }[] = [
  { key: 'net_goods',      label: '貨物貿易',  color: '#22c55e' },  // 緑
  { key: 'net_services',   label: 'サービス',  color: '#8b5cf6' },  // 紫
  { key: 'net_securities', label: '証券投資',  color: '#06b6d4' },  // シアン
  { key: 'net_other',      label: 'その他投資', color: '#6b7280' },  // グレー
]

// =============================================================================
// ユーティリティ
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

const formatValue = (v: number | null): string => {
  if (v == null) return '—'
  return v.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

// =============================================================================
// 最新値ボックスアイテム
// =============================================================================

function _LatestBox({
  label,
  value,
  color,
  isHidden,
  onClick,
}: {
  label: string
  value: number | null
  color: string
  isHidden: boolean
  onClick: () => void
}) {
  const isNegative = value != null && value < 0
  return (
    <div
      onClick={onClick}
      style={{
        cursor: 'pointer',
        opacity: isHidden ? 0.3 : 1,
        transition: 'opacity 0.2s',
        display: 'flex',
        alignItems: 'center',
        gap: 4,
      }}
    >
      <span style={{ fontSize: 11, color: '#999' }}>{label}</span>
      <span style={{
        fontSize: 16,
        fontWeight: 'bold',
        color: isNegative ? '#ef4444' : color,
      }}>
        {formatValue(value)}
      </span>
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnCapitalFlowsChart({ data }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>('overview')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(5)
  const { handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const sortedData = useSortedData(data?.data ?? [])
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2018,
  })

  const hasData = sortedData.length > 0

  const activeSeries = useMemo(() => {
    if (viewMode === 'overview') return OVERVIEW_SERIES
    return DETAIL_SERIES
  }, [viewMode])

  const lines = useMemo(() => {
    return activeSeries
      .filter(s => !isHidden(s.key))
      .map(s => ({
        dataKey: s.key,
        color: s.color,
        name: s.label,
      }))
  }, [activeSeries, isHidden])

  if (data === null) {
    return (
      <div id="capital-flows">
        <LoadingChart title="資本フロー（Capital Flows）" />
      </div>
    )
  }

  if (!hasData) {
    return (
      <div id="capital-flows">
        <ChartContainer title="資本フロー（Capital Flows）" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const latest = sortedData[sortedData.length - 1]

  return (
    <div id="capital-flows">
      <ChartContainer
        title="資本フロー"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="SAFE (国家外汇管理局)"
        sourceUrl="https://www.safe.gov.cn/safe/2018/0419/8806.html"
        handbookId="capital-flows"
      >
        {/* 最新値表示（クリックで系列トグル） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: '#999', fontWeight: 'bold' }}>
              最新値 ({latest?.date ? formatDateFull(latest.date) : ''})
            </span>
            {activeSeries.map(s => (
              <_LatestBox
                key={s.key}
                label={s.label}
                value={latest?.[s.key as keyof CnCapitalFlowsItem] as number | null ?? null}
                color={s.color}
                isHidden={isHidden(s.key)}
                onClick={() => handleLegendClick(s.key)}
              />
            ))}
          </div>
          <div style={{ fontSize: 11, color: '#999' }}>
            億USD（クリックで系列ON/OFF）
          </div>
        </div>

        {/* ViewModeButtonGroup + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup
            options={VIEW_MODE_OPTIONS}
            currentMode={viewMode}
            onChange={setViewMode}
          />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=cn_capital_flows', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* PeriodSelector */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={lines}
          yAxisFormatter={(v: number) => `${v.toLocaleString()}`}
          yDomain={['dataMin - 100', 'dataMax + 100']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateFull}
          tooltipValueFormatter={(v: number) =>
            `${v.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} 億USD`
          }
          showZeroLine={true}
          showLegend={false}
        />
      </ChartContainer>
    </div>
  )
}
