/**
 * ECB小売売上高チャートコンポーネント
 *
 * ECB Data APIからユーロ圏小売売上高データを取得し、表示
 *
 * データ:
 * - 小売売上高指数（営業日調整）
 * - 前月比変化率 (MoM): 季節・営業日調整済み
 * - 前年比変化率 (YoY): 営業日調整済み
 *
 * データソース:
 * - European Central Bank (ECB) - Short-Term Statistics
 *
 * 発表スケジュール:
 * - 毎月2日〜12日 18:00-18:10 CET
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
  useMonthlyTableData,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { ECBRetailTradeData } from '../../../../hooks/useDashboardData'

interface ECBRetailTradeChartProps {
  data: ECBRetailTradeData | null
}

interface ChartDataPoint {
  date: string
  yoy: number
  mom: number
  [key: string]: unknown
}

type DataKind = 'yoy' | 'mom'

type DisplayMode = 'chart' | 'heatmap'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// グラフの色
const COLORS = {
  yoy: '#1890ff',
  mom: '#52c41a',
}

export default function ECBRetailTradeChart({ data }: ECBRetailTradeChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  // propsのデータをチャート用に変換（前年比と前月比をマージ）
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const dateMap = new Map<string, ChartDataPoint>()

    // 前年比データをマージ
    if (data.retail_yoy) {
      data.retail_yoy.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, { date: point.date, yoy: 0, mom: 0 })
        }
        const existing = dateMap.get(point.date)!
        existing.yoy = point.value
      })
    }

    // 前月比データをマージ
    if (data.retail_mom) {
      data.retail_mom.forEach(point => {
        if (!dateMap.has(point.date)) {
          dateMap.set(point.date, { date: point.date, yoy: 0, mom: 0 })
        }
        const existing = dateMap.get(point.date)!
        existing.mom = point.value
      })
    }

    return Array.from(dateMap.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const momTableData = useMonthlyTableData(chartData, (item) => item.mom)

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="小売売上高（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="小売売上高（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-retail-trade-chart">
      <ChartContainer
        title="小売売上高（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="Eurostat"
        handbookId="ecb-retail-trade"
        sourceUrl="https://ec.europa.eu/eurostat/web/main/news/euro-indicators?p_p_id=estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageNumber=1&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_action=search&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_pageSize=11&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_text=retail+trade&_estatsearchportlet_WAR_estatsearchportlet_INSTANCE_OaTpFrwlabNK_collection=CAT_PREREL&p_auth=FdY2UEfx&text=Volume+of+retail+trade"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={dataKind === 'yoy' ? latest?.yoy : latest?.mom}
          valueColor={dataKind === 'yoy' ? COLORS.yoy : COLORS.mom}
          date={latest?.date}
          nextRelease={data.next_release}
          format="percent"
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
                  {/* 上段: 指標種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ecb_retail_trade_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（前月比のときのみ） */}
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 期間セレクター */}
                  {(dataKind === 'yoy' || (dataKind === 'mom' && displayMode === 'chart')) && (
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  )}

                  {/* コンテンツ表示 */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && <MonthlyTable data={momTableData} />}

                  {dataKind === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLORS.yoy, name: '小売売上高（前年比）', hide: hiddenSeries.has('yoy') },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      onLegendClick={handleLegendClick}
                    />
                  )}

                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLORS.mom, name: '小売売上高（前月比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ecb_retail_trade" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
