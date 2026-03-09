/**
 * オーストラリアGDP詳細チャートコンポーネント
 *
 * ABSからGDPデフレーター・純輸出寄与・設備投資・家計消費データを取得し表示
 *
 * データ:
 * - GDP Deflator QoQ / YoY
 * - Net Exports Contribution to GDP (ppt)
 * - Capital Expenditure (GFCF) QoQ/YoY/Level
 * - Household Consumption QoQ/YoY/Level
 *
 * データソース:
 * - ABS (Australian Bureau of Statistics) 5206.0 Table 2 & 5
 *
 * 発表スケジュール:
 * - 四半期ごと（National Accountsと同日）
 */
import { useState, useMemo, useCallback } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useQuarterlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { AuGdpPriceRelatedData } from '../../../../hooks/useDashboardData'

interface AuGdpPriceRelatedChartProps {
  data: AuGdpPriceRelatedData | null
}

interface ChartDataPoint {
  date: string
  deflator_qoq: number
  deflator_yoy: number
  net_exports_contribution: number
  exports_contribution: number
  imports_contribution: number
  gfcf_qoq: number
  gfcf_yoy: number
  gfcf_level: number
  consumption_qoq: number
  consumption_yoy: number
  consumption_level: number
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  deflator: '#E74C3C',           // 赤系
  net_exports: '#9B59B6',       // 紫
  exports: '#27AE60',           // 緑
  imports: '#E74C3C',           // 赤
  gfcf: '#3498DB',              // 青
  consumption: '#F39C12',       // オレンジ
}

type ViewMode =
  | 'deflator_qoq'
  | 'deflator_table'
  | 'deflator_yoy'
  | 'net_exports'
  | 'gfcf_qoq'
  | 'gfcf_table'
  | 'gfcf_yoy'
  | 'consumption_qoq'
  | 'consumption_table'
  | 'consumption_yoy'

// 四半期日付フォーマッター（2025-01-01 → 2025/Q1）
const formatQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const monthNum = parseInt(month, 10)
  const quarter = Math.ceil(monthNum / 3)
  return `${year}/Q${quarter}`
}

export default function AuGdpPriceRelatedChart({ data }: AuGdpPriceRelatedChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('deflator_qoq')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    deflator_qoq: 20,
    deflator_table: 20,
    deflator_yoy: 20,
    net_exports: 3,
    gfcf_qoq: 20,
    gfcf_table: 20,
    gfcf_yoy: 20,
    consumption_qoq: 20,
    consumption_table: 20,
    consumption_yoy: 20,
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      deflator_qoq: item.deflator_qoq ?? 0,
      deflator_yoy: item.deflator_yoy ?? 0,
      net_exports_contribution: item.net_exports_contribution ?? 0,
      exports_contribution: item.exports_contribution ?? 0,
      imports_contribution: item.imports_contribution ?? 0,
      gfcf_qoq: item.gfcf_qoq ?? 0,
      gfcf_yoy: item.gfcf_yoy ?? 0,
      gfcf_level: item.gfcf_level ?? 0,
      consumption_qoq: item.consumption_qoq ?? 0,
      consumption_yoy: item.consumption_yoy ?? 0,
      consumption_level: item.consumption_level ?? 0,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    return [...rawChartData].sort((a, b) => a.date.localeCompare(b.date))
  }, [rawChartData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ
  const deflatorExtractor = useCallback((item: ChartDataPoint) => item.deflator_qoq as number | null, [])
  const gfcfExtractor = useCallback((item: ChartDataPoint) => item.gfcf_qoq as number | null, [])
  const consumptionExtractor = useCallback((item: ChartDataPoint) => item.consumption_qoq as number | null, [])
  const deflatorTableData = useQuarterlyTableData(chartData, deflatorExtractor, 10)
  const gfcfTableData = useQuarterlyTableData(chartData, gfcfExtractor, 10)
  const consumptionTableData = useQuarterlyTableData(chartData, consumptionExtractor, 10)

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 現在表示中の値と表示ラベル
  const { currentValue, currentLabel, currentColor, currentFormat, currentDecimals, currentUnit } = useMemo(() => {
    if (!latest) return { currentValue: null, currentLabel: '', currentColor: COLORS.deflator, currentFormat: 'percent' as const, currentDecimals: 2, currentUnit: undefined as string | undefined }

    switch (viewMode) {
      case 'deflator_qoq':
      case 'deflator_table':
        return {
          currentValue: latest.deflator_qoq,
          currentLabel: 'GDPデフレーター（前期比）',
          currentColor: COLORS.deflator,
          currentFormat: 'percent' as const,
          currentDecimals: 2,
          currentUnit: undefined,
        }
      case 'deflator_yoy':
        return {
          currentValue: latest.deflator_yoy,
          currentLabel: 'GDPデフレーター（前年比）',
          currentColor: COLORS.deflator,
          currentFormat: 'percent' as const,
          currentDecimals: 2,
          currentUnit: undefined,
        }
      case 'net_exports':
        return {
          currentValue: latest.net_exports_contribution,
          currentLabel: '純輸出GDP寄与（前期比）',
          currentColor: COLORS.net_exports,
          currentFormat: 'percent' as const,
          currentDecimals: 2,
          currentUnit: 'ppt',
        }
      case 'gfcf_qoq':
      case 'gfcf_table':
        return {
          currentValue: latest.gfcf_qoq,
          currentLabel: '設備投資 GFCF（前期比）',
          currentColor: COLORS.gfcf,
          currentFormat: 'percent' as const,
          currentDecimals: 2,
          currentUnit: undefined,
        }
      case 'gfcf_yoy':
        return {
          currentValue: latest.gfcf_yoy,
          currentLabel: '設備投資 GFCF（前年比）',
          currentColor: COLORS.gfcf,
          currentFormat: 'percent' as const,
          currentDecimals: 2,
          currentUnit: undefined,
        }
      case 'consumption_qoq':
      case 'consumption_table':
        return {
          currentValue: latest.consumption_qoq,
          currentLabel: '家計消費（前期比）',
          currentColor: COLORS.consumption,
          currentFormat: 'percent' as const,
          currentDecimals: 2,
          currentUnit: undefined,
        }
      case 'consumption_yoy':
        return {
          currentValue: latest.consumption_yoy,
          currentLabel: '家計消費（前年比）',
          currentColor: COLORS.consumption,
          currentFormat: 'percent' as const,
          currentDecimals: 2,
          currentUnit: undefined,
        }
      default:
        return { currentValue: null, currentLabel: '', currentColor: COLORS.deflator, currentFormat: 'percent' as const, currentDecimals: 2, currentUnit: undefined }
    }
  }, [latest, viewMode])

  if (data === null) {
    return <LoadingChart title="GDP詳細" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP詳細" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // データ比較用のoverlayConfig ID
  const getCompareId = () => {
    switch (viewMode) {
      case 'deflator_qoq':
      case 'deflator_table': return 'au_gdp_deflator_qoq'
      case 'deflator_yoy': return 'au_gdp_deflator_yoy'
      case 'net_exports': return 'au_gdp_net_exports'
      case 'gfcf_qoq':
      case 'gfcf_table': return 'au_gdp_gfcf_qoq'
      case 'gfcf_yoy': return 'au_gdp_gfcf_yoy'
      case 'consumption_qoq':
      case 'consumption_table': return 'au_gdp_consumption_qoq'
      case 'consumption_yoy': return 'au_gdp_consumption_yoy'
      default: return 'au_gdp_deflator_qoq'
    }
  }

  const isTableMode = viewMode === 'deflator_table' || viewMode === 'gfcf_table' || viewMode === 'consumption_table'

  return (
    <div id="au-gdp-price-related-chart">
      <ChartContainer
        title="GDP詳細"
        showPeriodSelector={false}
        dataSource="ABS (Australian Bureau of Statistics)"
        sourceUrl="https://www.abs.gov.au/statistics/economy/national-accounts/australian-national-accounts-national-income-expenditure-and-product"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={currentLabel}
          value={currentValue}
          date={latest?.date}
          format={currentFormat}
          decimals={currentDecimals}
          valueColor={currentColor}
          nextRelease={data.next_release}
          dateFormatter={formatQuarterLabel}
          unit={currentUnit}
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
                  {/* ビューモード切替 */}
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(mode) => setViewMode(mode as ViewMode)}
                    options={[
                      { mode: 'consumption_qoq', label: '消費前期比' },
                      { mode: 'consumption_table', label: '消費（テーブル）' },
                      { mode: 'consumption_yoy', label: '消費前年比' },
                      { mode: 'deflator_qoq', label: 'デフレーター前期比' },
                      { mode: 'deflator_table', label: 'デフレーター（テーブル）' },
                      { mode: 'deflator_yoy', label: 'デフレーター前年比' },
                      { mode: 'gfcf_qoq', label: '設備投資前期比' },
                      { mode: 'gfcf_table', label: '設備投資（テーブル）' },
                      { mode: 'gfcf_yoy', label: '設備投資前年比' },
                      { mode: 'net_exports', label: '純輸出寄与' },
                    ]}
                  />

                  {/* 期間セレクター（テーブル以外で表示） */}
                  {!isTableMode && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open(`/compare?s=${getCompareId()}`, '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  )}

                  {/* === デフレーター 前期比チャート === */}
                  {viewMode === 'deflator_qoq' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'deflator_qoq', color: COLORS.deflator, name: 'GDPデフレーター（前期比%）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {/* === デフレーター テーブル === */}
                  {viewMode === 'deflator_table' && (
                    <QuarterlyTable
                      data={deflatorTableData}
                      decimals={2}
                      helperText="※ 直近10年間の前期比データ（単位: %）"
                    />
                  )}

                  {/* === デフレーター 前年比チャート === */}
                  {viewMode === 'deflator_yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'deflator_yoy', color: COLORS.deflator, name: 'GDPデフレーター（前年比%）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
                      showZeroLine={true}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {/* === 純輸出寄与 === */}
                  {viewMode === 'net_exports' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'exports_contribution', color: COLORS.exports, name: '輸出寄与（ppt）' },
                        { dataKey: 'imports_contribution', color: COLORS.imports, name: '輸入寄与（ppt）' },
                        { dataKey: 'net_exports_contribution', color: COLORS.net_exports, name: '純輸出寄与（ppt）' },
                      ]}
                      yAxisFormatter={(v) => `${v}ppt`}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {/* === GFCF 前期比チャート === */}
                  {viewMode === 'gfcf_qoq' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'gfcf_qoq', color: COLORS.gfcf, name: '設備投資 GFCF（前期比%）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {/* === GFCF テーブル === */}
                  {viewMode === 'gfcf_table' && (
                    <QuarterlyTable
                      data={gfcfTableData}
                      decimals={2}
                      helperText="※ 直近10年間の前期比データ（単位: %）"
                    />
                  )}

                  {/* === GFCF 前年比チャート === */}
                  {viewMode === 'gfcf_yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'gfcf_yoy', color: COLORS.gfcf, name: '設備投資 GFCF（前年比%）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 2', 'dataMax + 2']}
                      showZeroLine={true}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {/* === 家計消費 前期比チャート === */}
                  {viewMode === 'consumption_qoq' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'consumption_qoq', color: COLORS.consumption, name: '家計消費（前期比%）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}

                  {/* === 家計消費 テーブル === */}
                  {viewMode === 'consumption_table' && (
                    <QuarterlyTable
                      data={consumptionTableData}
                      decimals={2}
                      helperText="※ 直近10年間の前期比データ（単位: %）"
                    />
                  )}

                  {/* === 家計消費 前年比チャート === */}
                  {viewMode === 'consumption_yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'consumption_yoy', color: COLORS.consumption, name: '家計消費（前年比%）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      yDomain={['dataMin - 2', 'dataMax + 2']}
                      showZeroLine={true}
                      xAxisFormatter={formatQuarterLabel}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="au_gdp" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
