/**
 * 銀行貸し出し態度（SLOOS）マルチシリーズチャートコンポーネント
 *
 * C&I貸出基準/需要（大企業・中堅/中小企業）
 * CRE貸出基準/需要（NFNR/CLD/Multifamily）
 *
 * タブで切り替え:
 * 1. C&I 貸出基準（Tightening Standards）
 * 2. C&I 貸出需要（Stronger Demand）
 * 3. CRE 貸出基準
 * 4. CRE 貸出需要
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { BankLendingData, BankLendingSeriesData, BankLendingItem } from '../../../../hooks/useDashboardData'

import { usePeriodFiltering, formatQuarterLabel, type PeriodType } from '../common/useChartData'
import { NoDataMessage, SimpleLatestValueBox } from '../common/ChartComponents'
import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../common/chartConstants'

// =============================================================================
// 定数
// =============================================================================

interface SeriesConfig {
  key: string
  color: string
  name: string
}

const CI_STANDARDS_SERIES: SeriesConfig[] = [
  { key: 'ci_standards_large', color: '#ef4444', name: '大企業・中堅企業' },
  { key: 'ci_standards_small', color: '#f59e0b', name: '中小企業' },
]

const CI_DEMAND_SERIES: SeriesConfig[] = [
  { key: 'ci_demand_large', color: '#3b82f6', name: '大企業・中堅企業' },
  { key: 'ci_demand_small', color: '#8b5cf6', name: '中小企業' },
]

const CRE_STANDARDS_SERIES: SeriesConfig[] = [
  { key: 'cre_standards_nfnr', color: '#ef4444', name: '非住宅商業不動産 (NFNR)' },
  { key: 'cre_standards_cld', color: '#f59e0b', name: '建設・土地開発 (CLD)' },
  { key: 'cre_standards_mf', color: '#10b981', name: '集合住宅 (Multifamily)' },
]

const CRE_DEMAND_SERIES: SeriesConfig[] = [
  { key: 'cre_demand_nfnr', color: '#3b82f6', name: '非住宅商業不動産 (NFNR)' },
  { key: 'cre_demand_cld', color: '#8b5cf6', name: '建設・土地開発 (CLD)' },
  { key: 'cre_demand_mf', color: '#06b6d4', name: '集合住宅 (Multifamily)' },
]

// タブ定義
const TAB_CONFIG = [
  { key: 'ci_standards', label: 'C&I 貸出基準', series: CI_STANDARDS_SERIES },
  { key: 'ci_demand', label: 'C&I 貸出需要', series: CI_DEMAND_SERIES },
  { key: 'cre_standards', label: 'CRE 貸出基準', series: CRE_STANDARDS_SERIES },
  { key: 'cre_demand', label: 'CRE 貸出需要', series: CRE_DEMAND_SERIES },
] as const

// =============================================================================
// ヘルパー
// =============================================================================

interface MergedDataPoint {
  date: string
  value: number | null
  [key: string]: string | number | null | undefined
}

function mergeSeriesData(
  seriesMap: Record<string, BankLendingSeriesData> | undefined,
  seriesConfigs: SeriesConfig[],
): MergedDataPoint[] {
  if (!seriesMap) return []

  const dateSet = new Set<string>()
  for (const config of seriesConfigs) {
    const s = seriesMap[config.key]
    if (s?.data) {
      for (const d of s.data) {
        dateSet.add(d.date)
      }
    }
  }

  const dates = Array.from(dateSet).sort()
  const primaryKey = seriesConfigs[0]?.key

  return dates.map((date) => {
    const point: MergedDataPoint = { date, value: null }
    for (const config of seriesConfigs) {
      const s = seriesMap[config.key]
      const item = s?.data?.find((d: BankLendingItem) => d.date === date)
      point[config.key] = item?.value ?? null
    }
    point.value = (point[primaryKey] as number | null) ?? null
    return point
  })
}

function formatPercentage(value: number): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

// =============================================================================
// サブチャートコンポーネント（タブ内コンテンツ）
// =============================================================================

interface SubChartProps {
  seriesMap: Record<string, BankLendingSeriesData> | undefined
  seriesConfigs: SeriesConfig[]
  nextRelease?: { date: string; quarter: string; title: string } | null
}

function SLOOSSubChart({ seriesMap, seriesConfigs, nextRelease }: SubChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(20)

  const mergedData = useMemo(
    () => mergeSeriesData(seriesMap, seriesConfigs),
    [seriesMap, seriesConfigs],
  )

  const filteredData = usePeriodFiltering(mergedData, {
    selectedPeriod,
    defaultStartYear: 2000,
  })

  if (!mergedData.length) {
    return <NoDataMessage />
  }

  const latestValues = seriesConfigs.map((config) => {
    const s = seriesMap?.[config.key]
    return { ...config, latest: s?.latest }
  })

  const additionalLines = seriesConfigs.slice(1).map((config) => ({
    dataKey: config.key,
    color: config.color,
    name: config.name,
    strokeWidth: 2,
  }))

  return (
    <>
      {/* 最新値ボックス */}
      <div style={LATEST_VALUE_BOX_STYLE}>
        {latestValues.map((lv) => (
          <div key={lv.key} style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: TEXT_COLORS.secondary, marginBottom: 2 }}>
              {lv.name}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: lv.color }}>
                {lv.latest?.value != null ? formatPercentage(lv.latest.value) : '—'}
              </span>
              {lv.latest?.date && (
                <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
                  ({formatQuarterLabel(lv.latest.date)})
                </span>
              )}
            </div>
          </div>
        ))}
        {nextRelease && (
          <div style={{ fontSize: 11, color: TEXT_COLORS.secondary, whiteSpace: 'nowrap' }}>
            次回発表: {nextRelease.date}
          </div>
        )}
      </div>

      {/* 期間セレクタ + 比較ボタン（横並び） */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        <Tooltip title="比較ページを開く">
          <Button
            icon={<AreaChartOutlined />}
            onClick={() => window.open('/compare?s=bank_lending', '_blank')}
          >
            データ比較
          </Button>
        </Tooltip>
      </div>

      {/* チャート */}
      <ZoomableChart
        data={filteredData}
        dataKey={seriesConfigs[0].key}
        color={seriesConfigs[0].color}
        name={seriesConfigs[0].name}
        additionalLines={additionalLines}
        height={450}
        tickFormatter={formatPercentage}
        tooltipFormatter={formatPercentage}
        tooltipLabelFormatter={formatQuarterLabel}
        xAxisTickFormatter={formatQuarterLabel}
        enableDynamicTicks={true}
        showZeroLine={true}
        showFiftyLine={false}
        connectNulls={true}
      />
    </>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

interface BankLendingChartProps {
  data: BankLendingData | null
}

export default function BankLendingChart({ data }: BankLendingChartProps) {
  const [activeTab, setActiveTab] = useState('ci_standards')

  if (data === null) {
    return <LoadingChart title="銀行貸し出し態度（SLOOS）" />
  }

  const seriesMap = data.series

  // 後方互換: series がない場合は旧形式（単一シリーズ）
  if (!seriesMap || Object.keys(seriesMap).length === 0) {
    return <LegacySingleSeriesChart data={data} />
  }

  const tabItems = TAB_CONFIG.map((tab) => ({
    key: tab.key,
    label: tab.label,
    children: (
      <SLOOSSubChart
        seriesMap={seriesMap}
        seriesConfigs={tab.series as unknown as SeriesConfig[]}
        nextRelease={data.next_release}
      />
    ),
  }))

  return (
    <div id="bank-lending-chart">
      <ChartContainer
        title="銀行貸し出し態度（SLOOS）"
        showPeriodSelector={false}
        dataSource="FRED (Federal Reserve)"
        sourceUrl="https://www.federalreserve.gov/data/sloos.htm"
      >
        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          size="small"
          style={{ marginTop: 8 }}
        />
      </ChartContainer>
    </div>
  )
}

// =============================================================================
// 後方互換: 旧単一シリーズ表示
// =============================================================================

function LegacySingleSeriesChart({ data }: { data: BankLendingData }) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(20)

  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []
    return [...data.data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
    )
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2000,
  })

  if (!chartData.length) {
    return (
      <ChartContainer title="銀行貸し出し態度（SLOOS）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="bank-lending-chart">
      <ChartContainer
        title="銀行貸し出し態度（SLOOS：大企業・中堅企業向けC&I貸出基準）"
        showPeriodSelector={false}
        dataSource="FRED (Federal Reserve)"
        sourceUrl="https://www.federalreserve.gov/data/sloos.htm"
      >
        <SimpleLatestValueBox
          value={data.latest?.value}
          valueColor="#b70303"
          date={data.latest?.date}
          nextRelease={data.next_release ? { date: data.next_release.date, label: data.next_release.quarter } : null}
          format="percent"
          decimals={1}
          dateFormatter={formatQuarterLabel}
        />

        {/* 期間セレクタ + 比較ボタン（横並び） */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=bank_lending', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        <ZoomableChart
          data={filteredData}
          dataKey="value"
          color="#b70303"
          name="銀行貸し出し態度"
          height={450}
          tickFormatter={formatPercentage}
          tooltipFormatter={formatPercentage}
          tooltipLabelFormatter={formatQuarterLabel}
          xAxisTickFormatter={formatQuarterLabel}
          enableDynamicTicks={true}
          showZeroLine={true}
          showFiftyLine={false}
          connectNulls={true}
          hideLegend={true}
        />
      </ChartContainer>
    </div>
  )
}
