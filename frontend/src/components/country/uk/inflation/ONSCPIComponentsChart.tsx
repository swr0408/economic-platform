/**
 * UK ONS CPI項目別前年比チャートコンポーネント
 *
 * データ:
 * - DKL5: CPI Energy YoY (エネルギー)
 * - D7I7: CPI Electricity YoY (電気)
 * - D7G8: CPI Food & Non-alcoholic YoY (食品・ノンアルコール飲料)
 * - D7NN: CPI Services YoY (サービス)
 * - D7NM: CPI Goods YoY (商品)
 * - D7GQ: CPI Rent YoY (家賃)
 *
 * 表示モード:
 * - 前年比グラフ (YoY): 複数系列の折れ線グラフ
 *
 * データソース:
 * - ONS MM23 Dataset (Consumer Price Indices)
 *
 * 発表スケジュール:
 * - 毎月中旬（CPIと同日・FMPカレンダー）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip, Tabs } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  usePeriodFiltering,
  useHiddenSeries,
  formatDateLabel,
  formatDateLabelJP,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
} from '../../usa/common/ChartComponents'
import {
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  DARK_THEME,
} from '../../usa/common/chartConstants'

import type { ONSCPIHData } from '../../../../hooks/useDashboardData'

interface ONSCPIComponentsChartProps {
  data: ONSCPIHData | null
}

interface ChartDataPoint {
  date: string
  energy_yoy: number | null
  electricity_yoy: number | null
  food_yoy: number | null
  services_yoy: number | null
  goods_yoy: number | null
  rent_yoy: number | null
  [key: string]: unknown
}

// 系列設定
const SERIES_CONFIG = [
  { key: 'food_yoy', name: '食品・ノンアルコール飲料', color: '#2ecc71', yAxisId: 'right' },
  { key: 'services_yoy', name: 'サービス', color: '#f39c12', yAxisId: 'left' },
  { key: 'goods_yoy', name: '商品', color: '#3498db', yAxisId: 'right' },
  { key: 'rent_yoy', name: '家賃', color: '#722ed1', yAxisId: 'left' },
  { key: 'energy_yoy', name: 'エネルギー', color: '#e74c3c', yAxisId: 'right2' },
  { key: 'electricity_yoy', name: '電気', color: '#d7d32f', yAxisId: 'right2' },
]

// 初期非表示系列
const INITIAL_HIDDEN_SERIES = new Set(['energy_yoy', 'electricity_yoy'])

export default function ONSCPIComponentsChart({ data }: ONSCPIComponentsChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<number | 'default' | 'all'>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries(INITIAL_HIDDEN_SERIES)

  // propsのデータをチャート用に変換（全系列をマージ）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.series) return []

    const dateMap = new Map<string, ChartDataPoint>()

    const initPoint = (date: string): ChartDataPoint => ({
      date,
      energy_yoy: null,
      electricity_yoy: null,
      food_yoy: null,
      services_yoy: null,
      goods_yoy: null,
      rent_yoy: null,
    })

    // 各系列のデータをマージ
    const seriesKeys = ['energy_yoy', 'electricity_yoy', 'food_yoy', 'services_yoy', 'goods_yoy', 'rent_yoy'] as const

    for (const key of seriesKeys) {
      const seriesData = data.series[key]?.data
      if (seriesData) {
        for (const point of seriesData) {
          if (!dateMap.has(point.date)) {
            dateMap.set(point.date, initPoint(point.date))
          }
          const dp = dateMap.get(point.date)!
          dp[key] = point.value
        }
      }
    }

    return Array.from(dateMap.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(rawChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  const hasData = rawChartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (rawChartData.length === 0) return null
    return rawChartData[rawChartData.length - 1]
  }, [rawChartData])

  const nextRelease = data?.next_release

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="CPI項目別前年比" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="CPI項目別前年比" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest) return []

    const items = []
    if (latest.services_yoy !== null) {
      items.push({
        label: 'サービス（前年比）',
        value: `${latest.services_yoy >= 0 ? '+' : ''}${latest.services_yoy.toFixed(1)}%`,
        color: latest.services_yoy >= 0 ? '#f5222d' : '#52c41a',
      })
    }
    if (latest.goods_yoy !== null) {
      items.push({
        label: '商品（前年比）',
        value: `${latest.goods_yoy >= 0 ? '+' : ''}${latest.goods_yoy.toFixed(1)}%`,
        color: latest.goods_yoy >= 0 ? '#f5222d' : '#52c41a',
      })
    }
    return items
  }

  // データ比較ページを開く
  const handleCompare = () => {
    window.open('/compare?s=uk_cpi_services_yoy&s=uk_cpi_goods_yoy&s=uk_cpi_food_yoy', '_blank')
  }

  // カスタムTooltip
  const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ dataKey: string; value: number; color: string; name: string }>; label?: string }) => {
    if (!active || !payload || payload.length === 0) return null

    return (
      <div style={{
        backgroundColor: DARK_THEME.bgTertiary,
        border: `1px solid ${DARK_THEME.border}`,
        borderRadius: 4,
        padding: '8px 12px',
      }}>
        <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
          {formatDateLabelJP(label || '')}
        </div>
        {payload.map((item, index) => (
          <div key={index} style={{ color: item.color, fontSize: 13, marginBottom: 4 }}>
            {item.name}: {item.value >= 0 ? '+' : ''}{item.value.toFixed(1)}%
          </div>
        ))}
      </div>
    )
  }

  return (
    <div id="uk-ons-cpi-components-chart">
      <ChartContainer
        title="CPI項目別前年比"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/economy/inflationandpriceindices"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
        />

        <Tabs
          defaultActiveKey="chart"
          items={[
            {
              key: 'chart',
              label: '時系列',
              children: (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <AntTooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={handleCompare}
                      >
                        データ比較
                      </Button>
                    </AntTooltip>
                  </div>
                  <ResponsiveContainer width="100%" height={450}>
                    <LineChart data={filteredData} margin={CHART_MARGIN}>
                      <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                      <XAxis
                        dataKey="date"
                        tickFormatter={formatDateLabel}
                        tick={AXIS_STYLE.tick}
                        interval={AXIS_STYLE.interval}
                      />
                      <YAxis
                        yAxisId="left"
                        tick={AXIS_STYLE.tick}
                        tickFormatter={(v: number) => `${v}%`}
                        domain={['auto', 'auto']}
                      />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        tick={AXIS_STYLE.tick}
                        tickFormatter={(v: number) => `${v}%`}
                        domain={['auto', 'auto']}
                      />
                      <YAxis
                        yAxisId="right2"
                        orientation="right"
                        tick={AXIS_STYLE.tick}
                        tickFormatter={(v: number) => `${v}%`}
                        domain={['auto', 'auto']}
                        width={20}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend
                        onClick={(e) => handleLegendClick(e.dataKey as string)}
                        wrapperStyle={{ cursor: 'pointer' }}
                      />
                      <ReferenceLine y={0} stroke="#666" strokeWidth={1} yAxisId="left" />

                      {SERIES_CONFIG.map(config => (
                        <Line
                          key={config.key}
                          type="monotone"
                          dataKey={config.key}
                          name={config.name}
                          stroke={config.color}
                          strokeWidth={2}
                          dot={false}
                          yAxisId={config.yAxisId}
                          connectNulls
                          hide={hiddenSeries.has(config.key)}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ons_cpih" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
