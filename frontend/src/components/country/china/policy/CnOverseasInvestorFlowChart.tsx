/**
 * 中国 海外投資家フロー（Foreign Holdings）チャートコンポーネント
 *
 * 3系列同時表示:
 * - SHCH: Shanghai Clearing House 保有残高 (RMB billion)
 * - CCDC: China Central Depository & Clearing 保有残高 (RMB billion)
 * - Total: 合計 (RMB billion)
 *
 * データソース: Bond Connect
 * https://www.chinabondconnect.com/en/Resource/Market-Data.html
 *
 * FMPマッピング: なし
 */
import { useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

import type { CnOverseasInvestorFlowData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnOverseasInvestorFlowData | null
}

type SeriesKey = 'shch' | 'ccdc' | 'total'

const SERIES_CONFIG: { key: SeriesKey; label: string; color: string }[] = [
  { key: 'total', label: 'Total',  color: '#3b82f6' },    // 青
  { key: 'ccdc',  label: 'CCDC',   color: '#10b981' },    // 緑
  { key: 'shch',  label: 'SHCH',   color: '#f59e0b' },    // オレンジ
]

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
  return (
    <div
      onClick={onClick}
      style={{
        cursor: 'pointer',
        opacity: isHidden ? 0.3 : 1,
        transition: 'opacity 0.2s',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}
    >
      <span style={{ fontSize: 12, color: '#999' }}>{label}</span>
      <span style={{ fontSize: 18, fontWeight: 'bold', color }}>
        {value != null ? `${value.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}` : '—'}
      </span>
      <span style={{ fontSize: 11, color: '#999' }}>RMB bn</span>
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnOverseasInvestorFlowChart({ data }: Props) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const { handleLegendClick, isHidden } = useHiddenSeries<SeriesKey>()

  const sortedData = useSortedData(data?.data ?? [])
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2019,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return (
      <div id="overseas-investor-flow">
        <LoadingChart title="海外投資家フロー" />
      </div>
    )
  }

  if (!hasData) {
    return (
      <div id="overseas-investor-flow">
        <ChartContainer title="海外投資家フロー" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const latest = sortedData[sortedData.length - 1]

  // 表示用ライン（非表示の系列を除外）
  const lines = SERIES_CONFIG
    .filter(s => !isHidden(s.key))
    .map(s => ({
      dataKey: s.key,
      color: s.color,
      name: s.label,
    }))

  return (
    <div id="overseas-investor-flow">
      <ChartContainer
        title="海外投資家フロー"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="Bond Connect"
        sourceUrl="https://www.chinabondconnect.com/en/Resource/Market-Data.html"
      >
        {/* 最新値表示（クリックで系列トグル） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: '#999', fontWeight: 'bold' }}>最新値</span>
            {SERIES_CONFIG.map(s => (
              <_LatestBox
                key={s.key}
                label={s.label}
                value={latest?.[s.key] ?? null}
                color={s.color}
                isHidden={isHidden(s.key)}
                onClick={() => handleLegendClick(s.key)}
              />
            ))}
          </div>
          <div style={{ fontSize: 11, color: '#999' }}>
            {latest?.date ? formatDateFull(latest.date) : ''}
          </div>
        </div>

        {/* データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=cn_overseas_investor_flow', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間セレクター */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={lines}
          yAxisFormatter={(v: number) => `${v.toLocaleString()}`}
          yDomain={['dataMin - 200', 'dataMax + 200']}
          xAxisFormatter={formatDateLabel}
          tooltipLabelFormatter={formatDateFull}
          tooltipValueFormatter={(v: number) => `${v.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} bn`}
          showZeroLine={false}
          showLegend={false}
        />
      </ChartContainer>
    </div>
  )
}
