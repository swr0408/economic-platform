/**
 * ユーロ圏GDP構成要素別寄与度チャートコンポーネント
 *
 * ECB APIからGDP構成要素データを取得し、積み上げ棒グラフで表示
 *
 * 構成要素:
 * - Private Consumption (民間消費)
 * - Government Consumption (政府消費)
 * - Gross Fixed Capital Formation (総固定資本形成)
 * - Changes in Inventories (在庫変動)
 * - Net Exports (純輸出)
 *
 * データソース:
 * - European Central Bank (ECB) - Main National Accounts
 *
 * 発表スケジュール:
 * - 毎日18:00 CET更新
 */
import { useState, useMemo } from 'react'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
} from 'recharts'

import { type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage } from '../../usa/common/ChartComponents'
import { DARK_THEME, TEXT_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

import type { ECBGDPComponentsData } from '../../../../hooks/useDashboardData'

interface EuroGDPComponentsChartProps {
  data: ECBGDPComponentsData | null
}

type ComponentKey = 'privateConsumption' | 'governmentConsumption' | 'grossFixedCapital' | 'changesInInventories' | 'netExports'

interface ChartDataPoint {
  date: string
  privateConsumption?: number
  governmentConsumption?: number
  grossFixedCapital?: number
  changesInInventories?: number
  netExports?: number
}

// 構成要素ごとの色
const COMPONENT_COLORS: Record<ComponentKey, string> = {
  privateConsumption: '#3B82F6',      // 青
  governmentConsumption: '#8B5CF6',   // 紫
  grossFixedCapital: '#F59E0B',       // 黄
  changesInInventories: '#06B6D4',    // シアン
  netExports: '#ce3d3d',              // 緑
}

// 構成要素の日本語名
const COMPONENT_NAMES: Record<ComponentKey, string> = {
  privateConsumption: '民間消費',
  governmentConsumption: '政府消費',
  grossFixedCapital: '総固定資本形成',
  changesInInventories: '在庫変動',
  netExports: '純輸出',
}

// ECB四半期形式（2024-Q3）用のフォーマッター
const formatECBQuarterLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  return dateStr.replace('-Q', '/Q')
}

// ECB四半期形式から年を抽出
const getYearFromECBQuarter = (dateStr: string): number => {
  const match = dateStr.match(/^(\d{4})-Q\d$/)
  return match ? parseInt(match[1], 10) : 0
}

export default function EuroGDPComponentsChart({ data }: EuroGDPComponentsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [hiddenSeries, setHiddenSeries] = useState<Set<ComponentKey>>(new Set())

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data || !data.components) return []

    const dateMap = new Map<string, ChartDataPoint>()

    // 各構成要素のデータをマージ
    data.components.private_consumption?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, { date: point.date })
      }
      const existing = dateMap.get(point.date)!
      existing.privateConsumption = point.value || 0
    })

    data.components.government_consumption?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, { date: point.date })
      }
      const existing = dateMap.get(point.date)!
      existing.governmentConsumption = point.value || 0
    })

    data.components.gross_fixed_capital?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, { date: point.date })
      }
      const existing = dateMap.get(point.date)!
      existing.grossFixedCapital = point.value || 0
    })

    data.components.changes_in_inventories?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, { date: point.date })
      }
      const existing = dateMap.get(point.date)!
      existing.changesInInventories = point.value || 0
    })

    data.components.net_exports?.forEach(point => {
      if (!dateMap.has(point.date)) {
        dateMap.set(point.date, { date: point.date })
      }
      const existing = dateMap.get(point.date)!
      existing.netExports = point.value || 0
    })

    // 日付でソート
    const result = Array.from(dateMap.values()).sort((a, b) => a.date.localeCompare(b.date))
    return result
  }, [data])

  // 期間フィルタリング
  const filteredData = useMemo(() => {
    if (!chartData.length) return []

    const now = new Date()
    const currentYear = now.getFullYear()

    let startYear: number
    if (selectedPeriod === 'all') {
      return chartData
    } else if (selectedPeriod === 'default') {
      startYear = 2015
    } else if (typeof selectedPeriod === 'number') {
      startYear = currentYear - selectedPeriod
    } else {
      startYear = 2015
    }

    return chartData.filter(item => {
      const year = getYearFromECBQuarter(item.date)
      return year >= startYear
    })
  }, [chartData, selectedPeriod])

  // 最新のデータポイントを取得
  const latestData = useMemo(() => {
    if (!filteredData.length) return null
    const latest = filteredData[filteredData.length - 1]

    // 合計を計算
    const total =
      (latest.privateConsumption || 0) +
      (latest.governmentConsumption || 0) +
      (latest.grossFixedCapital || 0) +
      (latest.changesInInventories || 0) +
      (latest.netExports || 0)

    return {
      date: latest.date,
      total,
      components: latest,
    }
  }, [filteredData])

  const hasData = chartData.length > 0

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="GDP構成要素別寄与度（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP構成要素別寄与度（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // レジェンドクリックでシリーズの表示/非表示を切り替え
  const handleLegendClick = (dataKey: string) => {
    const key = dataKey as ComponentKey
    setHiddenSeries(prev => {
      const newSet = new Set(prev)
      if (newSet.has(key)) {
        newSet.delete(key)
      } else {
        newSet.add(key)
      }
      return newSet
    })
  }

  // Tooltipのフォーマッター
  const tooltipFormatter = (value: number, name: string) => {
    const formatted = value.toFixed(2)
    return [`${value >= 0 ? '+' : ''}${formatted}%`, name]
  }

  // Tooltipのラベルフォーマッター
  const tooltipLabelFormatter = (label: string) => formatECBQuarterLabel(label)

  return (
    <div id="euro-gdp-components-chart">
      <ChartContainer
        title="GDP構成要素別寄与度（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="European Central Bank (ECB)"
        sourceUrl="https://ec.europa.eu/eurostat/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=CCS941kV&text=GDP"
      >
        {/* 最新値表示 */}
        {latestData && (
          <div style={LATEST_VALUE_BOX_STYLE}>
            <div>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>最新値（合計寄与度）: </span>
              <span
                style={{
                  fontSize: 18,
                  fontWeight: 'bold',
                  color: latestData.total >= 0 ? TEXT_COLORS.positive : TEXT_COLORS.negative,
                }}
              >
                {latestData.total >= 0 ? '+' : ''}{latestData.total.toFixed(2)}%
              </span>
              <span style={{ fontSize: 12, color: TEXT_COLORS.tertiary, marginLeft: 8 }}>
                ({formatECBQuarterLabel(latestData.date)})
              </span>
            </div>
          </div>
        )}

        {/* 期間セレクター */}
        <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
        </div>

        {/* チャート */}
        <div style={{ width: '100%', height: 450 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={filteredData}
              margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
              stackOffset="sign"
            >
              <CartesianGrid strokeDasharray="3 3" stroke={DARK_THEME.border} />
              <XAxis
                dataKey="date"
                stroke={DARK_THEME.textSecondary}
                fontSize={12}
                tickFormatter={formatECBQuarterLabel}
              />
              <YAxis
                stroke={DARK_THEME.textSecondary}
                fontSize={12}
                tickFormatter={(v) => `${v}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: DARK_THEME.bgSecondary,
                  border: `1px solid ${DARK_THEME.border}`,
                  borderRadius: 6,
                  color: DARK_THEME.textPrimary,
                }}
                formatter={tooltipFormatter}
                labelFormatter={tooltipLabelFormatter}
              />
              <Legend
                onClick={(e) => handleLegendClick(e.dataKey as string)}
                wrapperStyle={{ cursor: 'pointer' }}
              />
              <ReferenceLine y={0} stroke={DARK_THEME.textSecondary} strokeWidth={1.5} />

              <Bar
                dataKey="privateConsumption"
                name={COMPONENT_NAMES.privateConsumption}
                stackId="total"
                fill={COMPONENT_COLORS.privateConsumption}
                hide={hiddenSeries.has('privateConsumption')}
              />
              <Bar
                dataKey="governmentConsumption"
                name={COMPONENT_NAMES.governmentConsumption}
                stackId="total"
                fill={COMPONENT_COLORS.governmentConsumption}
                hide={hiddenSeries.has('governmentConsumption')}
              />
              <Bar
                dataKey="grossFixedCapital"
                name={COMPONENT_NAMES.grossFixedCapital}
                stackId="total"
                fill={COMPONENT_COLORS.grossFixedCapital}
                hide={hiddenSeries.has('grossFixedCapital')}
              />
              <Bar
                dataKey="changesInInventories"
                name={COMPONENT_NAMES.changesInInventories}
                stackId="total"
                fill={COMPONENT_COLORS.changesInInventories}
                hide={hiddenSeries.has('changesInInventories')}
              />
              <Bar
                dataKey="netExports"
                name={COMPONENT_NAMES.netExports}
                stackId="total"
                fill={COMPONENT_COLORS.netExports}
                hide={hiddenSeries.has('netExports')}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </ChartContainer>
    </div>
  )
}
