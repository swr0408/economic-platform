/**
 * OECD CLI（景気先行指数）マルチシリーズチャート
 *
 * 11ヶ国/地域のComposite Leading Indicatorsを表示
 * 初期非表示: Korea, Australia, Canada
 *
 * データソース: OECD SDMX API
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../../usa/common/chartConstants'
import { usePeriodFiltering } from '../../usa/common/useChartData'
import { NoDataMessage } from '../../usa/common/ChartComponents'
import type { PeriodValue } from '../../../common/PeriodSelector'

import type { OecdCliData, OecdCliItem } from '../../../../hooks/useDashboardData'

// =============================================================================
// 定数
// =============================================================================

interface SeriesConfig {
  key: string
  label: string
  color: string
}

const CLI_SERIES: SeriesConfig[] = [
  { key: 'g20', label: 'G20', color: '#3b82f6' },         // 青
  { key: 'g7', label: 'G7', color: '#10b981' },            // 緑
  { key: 'a5m', label: 'Major Five Asia', color: '#f97316' }, // オレンジ
  { key: 'usa', label: 'USA', color: '#ef4444' },          // 赤
  { key: 'jpn', label: 'Japan', color: '#ec4899' },        // ピンク
  { key: 'chn', label: 'China', color: '#eab308' },        // 黄
  { key: 'deu', label: 'Germany', color: '#8b5cf6' },      // 紫
  { key: 'gbr', label: 'UK', color: '#06b6d4' },           // シアン
  { key: 'kor', label: 'Korea', color: '#a3e635' },        // ライム
  { key: 'aus', label: 'Australia', color: '#fb923c' },    // ライトオレンジ
  { key: 'can', label: 'Canada', color: '#38bdf8' },       // スカイブルー
]

// 初期表示: G20, G7, Major Five Asia, USA のみ
const INITIALLY_HIDDEN = ['jpn', 'chn', 'deu', 'gbr', 'kor', 'aus', 'can']

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatValue = (value: number) => value.toFixed(2)

// =============================================================================
// メインコンポーネント
// =============================================================================

interface Props {
  data: OecdCliData | null
}

export default function OecdCliChart({ data }: Props) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set(INITIALLY_HIDDEN))

  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []
    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map(item => ({
        ...item,
        value: item.g20, // ZoomableChart requires 'value' field
      }))
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  const handleLegendClick = (dataKey: string) => {
    setHiddenSeries(prev => {
      const next = new Set(prev)
      if (next.has(dataKey)) {
        next.delete(dataKey)
      } else {
        next.add(dataKey)
      }
      return next
    })
  }

  if (data === null) {
    return (
      <div id="oecd-cli">
        <LoadingChart title="OECD CLI（景気先行指数）" />
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div id="oecd-cli">
        <ChartContainer title="OECD CLI（景気先行指数）" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const latest = data.latest

  // ZoomableChart用: 最初のシリーズをmainとし、残りはadditionalLines
  const primarySeries = CLI_SERIES[0]
  const additionalLines = CLI_SERIES.slice(1).map(s => ({
    dataKey: s.key,
    color: s.color,
    name: s.label,
    strokeWidth: 2,
  }))

  return (
    <div id="oecd-cli">
      <ChartContainer
        title="OECD CLI（景気先行指数）"
        showPeriodSelector={false}
        dataSource="OECD"
        sourceUrl="https://www.oecd.org/en/data/datasets/oecd-composite-leading-indicators-clis.html"
        handbookId="oecd-cli"
      >
        {/* 最新値ボックス */}
        <div style={{ ...LATEST_VALUE_BOX_STYLE, justifyContent: 'flex-start' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {latest?.date && (
              <span style={{ fontSize: 11, color: TEXT_COLORS.secondary, marginRight: 4 }}>
                {formatDateLabel(latest.date)}
              </span>
            )}
            {CLI_SERIES.map(s => (
              <_LatestBox
                key={s.key}
                label={s.label}
                value={latest?.[s.key as keyof OecdCliItem] as number | null | undefined}
                color={s.color}
                hidden={hiddenSeries.has(s.key)}
                onClick={() => handleLegendClick(s.key)}
              />
            ))}
          </div>
        </div>

        {/* 期間セレクタ + 比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=oecd_cli', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート */}
        <ZoomableChart
          data={filteredData}
          dataKey={primarySeries.key}
          color={primarySeries.color}
          name={primarySeries.label}
          additionalLines={additionalLines}
          initialHiddenLines={INITIALLY_HIDDEN}
          height={450}
          tickFormatter={formatValue}
          tooltipFormatter={formatValue}
          tooltipLabelFormatter={formatDateLabel}
          xAxisTickFormatter={formatDateLabel}
          enableDynamicTicks={true}
          showZeroLine={false}
          showFiftyLine={true}
          fiftyLineValue={100}
          connectNulls={true}
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
  const formatted = value != null ? value.toFixed(2) : '—'

  return (
    <span
      onClick={onClick}
      style={{
        cursor: 'pointer',
        opacity: hidden ? 0.3 : 1,
        marginRight: 4,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 3,
      }}
    >
      <span
        style={{
          display: 'inline-block',
          width: 8,
          height: 8,
          borderRadius: '50%',
          backgroundColor: color,
        }}
      />
      <span style={{ fontSize: 11, color: TEXT_COLORS.secondary }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 700, color }}>
        {formatted}
      </span>
    </span>
  )
}
