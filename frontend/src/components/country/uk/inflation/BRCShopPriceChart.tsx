/**
 * BRC店頭価格指数チャートコンポーネント
 *
 * データ:
 * - BRC Shop Price Index YoY（前年比）
 *
 * 表示モード:
 * - 前年比グラフ (YoY): 単一系列の折れ線グラフ
 * - 前年比テーブル (YoY Table): 月別テーブル
 *
 * データソース:
 * - CSV (2010年〜過去データ)
 * - FMP (最新値更新用)
 *
 * 発表スケジュール:
 * - 毎月末〜翌月初
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip, Tabs } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
  formatDateLabel,
  formatDateLabelJP,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import {
  CHANGE_LEGEND_10PCT,
  getChangeCellColor10pct,
} from '../../usa/common/chartConstants'

import type { BRCShopPriceData } from '../../../../hooks/useDashboardData'

interface BRCShopPriceChartProps {
  data: BRCShopPriceData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// グラフの色
const CHART_COLOR = '#e74c3c' // 赤系

export default function BRCShopPriceChart({ data }: BRCShopPriceChartProps) {
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(displayMode, {
    chart: 10,
    heatmap: 10,
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map(point => ({
      date: point.date,
      value: point.value,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2020,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const yoyTableData = useMonthlyTableData(chartData, (item) => item.value)

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (chartData.length === 0) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  const nextRelease = data?.next_release

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="BRC店頭価格指数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="BRC店頭価格指数" showPeriodSelector={false} showDataSource={false} handbookId="uk-brc-shop-price">
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    if (!latest || latest.value === null) return []

    return [
      {
        label: 'BRC店頭価格指数（前年比）',
        value: `${latest.value >= 0 ? '+' : ''}${latest.value.toFixed(1)}%`,
        color: latest.value >= 0 ? '#f5222d' : '#52c41a',
      },
    ]
  }

  // データ比較ページを開く
  const handleCompare = () => {
    window.open('/compare?s=uk_brc_shop_price_yoy', '_blank')
  }

  return (
    <div id="uk-brc-shop-price-chart">
      <ChartContainer
        title="BRC店頭価格指数（前年比）"
        showPeriodSelector={false}
        dataSource="BRC"
        sourceUrl="https://brc.org.uk/news-and-events/news/?contentType=2028&pageIndex=3"
        handbookId="uk-brc-shop-price"
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
                  {/* 表示形式切り替え */}
                  <div style={{ marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                  </div>

                  {/* 前年比グラフ */}
                  {displayMode === 'chart' && (
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
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          {
                            dataKey: 'value',
                            color: CHART_COLOR,
                            name: 'BRC店頭価格指数',
                            hide: false,
                          },
                        ]}
                        xAxisFormatter={formatDateLabel}
                        yAxisFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                        tooltipLabelFormatter={formatDateLabelJP}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        showZeroLine
                      />
                    </>
                  )}

                  {/* 前年比テーブル */}
                  {displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={yoyTableData}
                      getCellBgColor={getChangeCellColor10pct}
                      legendItems={CHANGE_LEGEND_10PCT}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="brc_shop_price" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
