/**
 * 中国・上海コンテナ運賃指数（SCFI / CCFI）チャートコンポーネント
 *
 * 2系列:
 * - scfi: Shanghai Containerized Freight Index（上海輸出コンテナ運賃指数）
 * - ccfi: China Containerized Freight Index（中国輸出コンテナ運賃指数）
 *
 * データソース: Shanghai Shipping Exchange (SSE)
 * - SCFI: https://en.sse.net.cn/indices/scfinew.jsp
 * - CCFI: https://en.sse.net.cn/indices/ccfinew.jsp
 *
 * FMPマッピング: なし（マーケットインパクトタブなし）
 */
import { useState } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { ChinaShanghaiContainerFreightIndexData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: ChinaShanghaiContainerFreightIndexData | null
}

const COLOR_SCFI = '#0EA5E9'  // Sky blue
const COLOR_CCFI = '#F97316'  // Orange

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const parts = dateStr.split('-')
  return `${parts[0]}年${parseInt(parts[1])}月${parseInt(parts[2])}日`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ChinaShanghaiContainerFreightIndexChart({ data }: Props) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<string>()

  const sortedData = useSortedData(data?.data ?? [])
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  // ローディング
  if (data === null) {
    return (
      <div id="container-freight-index">
        <LoadingChart title="コンテナ運賃指数" />
      </div>
    )
  }

  if (!hasData) {
    return (
      <div id="container-freight-index">
        <ChartContainer title="コンテナ運賃指数" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const latest = data.latest

  return (
    <div id="container-freight-index">
      <ChartContainer
        title="コンテナ運賃指数"
        showPeriodSelector={false}
        dataSource="Shanghai Shipping Exchange (SSE)"
        sourceUrl="https://en.sse.net.cn/indices/scfinew.jsp"
      >
        {/* 最新値ボックス */}
        <div style={{ ...LATEST_VALUE_BOX_STYLE, justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {latest?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDateFull(latest.date)}
              </span>
            )}
            <_LatestBox
              label="SCFI"
              value={latest?.scfi}
              color={COLOR_SCFI}
              hidden={hiddenSeries.has('scfi')}
              onClick={() => handleLegendClick('scfi')}
            />
            <_LatestBox
              label="CCFI"
              value={latest?.ccfi}
              color={COLOR_CCFI}
              hidden={hiddenSeries.has('ccfi')}
              onClick={() => handleLegendClick('ccfi')}
            />
          </div>
        </div>

        {/* データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=china_shanghai_container_freight_index', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間選択 */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'scfi', color: COLOR_SCFI, name: 'SCFI', hide: hiddenSeries.has('scfi') },
            { dataKey: 'ccfi', color: COLOR_CCFI, name: 'CCFI', hide: hiddenSeries.has('ccfi') },
          ]}
          xAxisFormatter={formatDateLabel}
          yAxisFormatter={(v: number) => `${v.toLocaleString()}`}
          tooltipLabelFormatter={formatDateFull}
          tooltipValueFormatter={(v: number) => v != null ? `${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'N/A'}
          yDomain={['dataMin - 100', 'dataMax + 100']}
          showZeroLine={false}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}

// =============================================================================
// サブコンポーネント
// =============================================================================

function _LatestBox({
  label,
  value,
  color,
  hidden,
  onClick,
}: {
  label: string
  value: number | null | undefined
  color: string
  hidden: boolean
  onClick: () => void
}) {
  const formatted = value != null
    ? value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '—'

  return (
    <span
      onClick={onClick}
      style={{
        cursor: 'pointer',
        opacity: hidden ? 0.3 : 1,
        marginRight: 8,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
      }}
    >
      <span
        style={{
          display: 'inline-block',
          width: 10,
          height: 10,
          borderRadius: '50%',
          backgroundColor: color,
        }}
      />
      <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 700, color }}>
        {formatted}
      </span>
    </span>
  )
}
