/**
 * 韓国半導体輸出チャートコンポーネント
 *
 * データ:
 * - value: 輸出額（Billion USD）
 * - yoy: 前年比 (%)
 * - mom: 前月比 (%)
 *
 * データソース:
 * - MOTIE ICT 수출입 동향
 *
 * FMPマッピング: south_korean_exports (KR / Exports YoY) を流用
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

import type { KrSemiconductorExportsData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface SouthKoreanSemiconductorExportsChartProps {
  data: KrSemiconductorExportsData | null
}

type ViewMode = 'raw' | 'yoy' | 'mom'
type DisplayMode = 'chart' | 'heatmap'
type ActiveTab = 'timeseries' | 'market_impact'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string }[] = [
  { mode: 'raw', label: '水準' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

const COLOR_VALUE = '#E11D48'   // rose-600
const COLOR_YOY = '#059669'     // emerald-600
const COLOR_MOM = '#2563EB'     // blue-600

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function SouthKoreanSemiconductorExportsChart({ data }: SouthKoreanSemiconductorExportsChartProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('raw')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    raw: 'all',
    yoy: 'all',
    mom: 3,
  })

  const sortedData = useSortedData(data?.data ?? [])

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2023,
  })

  // ヒートマップ用データ（前月比）
  const momTableData = useMonthlyTableData(
    sortedData,
    (item: { mom?: number | null }) => item.mom ?? null,
  )

  const hasData = sortedData.length > 0

  const latest = useMemo(() => {
    if (!sortedData.length) return null
    return sortedData[sortedData.length - 1]
  }, [sortedData])

  if (data === null) {
    return <LoadingChart title="韓国半導体輸出" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="韓国半導体輸出" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latestValue = viewMode === 'raw' ? latest?.value : viewMode === 'yoy' ? latest?.yoy : latest?.mom
  const latestColor = viewMode === 'raw' ? COLOR_VALUE : viewMode === 'yoy' ? COLOR_YOY : COLOR_MOM
  const latestUnit = viewMode === 'raw' ? 'Billion USD' : '%'
  const latestDecimals = viewMode === 'raw' ? 2 : 1

  return (
    <div id="korea-semiconductor-exports">
      <ChartContainer
        title="韓国半導体輸出"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="MOTIE ICT 수출입 동향"
        sourceUrl="https://www.motir.go.kr/kor/article/ATCL3f49a5a8c?mno=&pageIndex=1&rowPageC=0&displayAuthor=&searchCategory=0&schClear=on&startDtD=&endDtD=&searchCondition=1&searchKeyword=%EC%88%98%EC%B6%9C%EC%9E%85+%EB%8F%99%ED%96%A5#"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="韓国半導体輸出"
          value={latestValue}
          valueColor={latestColor}
          date={latest?.date}
          decimals={latestDecimals}
          unit={latestUnit}
          nextRelease={data.next_release ?? undefined}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as ActiveTab)}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* ViewModeButtonGroup + データ比較ボタン（同一行） */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={VIEW_MODE_OPTIONS} currentMode={viewMode} onChange={setViewMode} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=south_korean_semiconductor_exports', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート/ヒートマップ切替（前月比のときのみ） */}
                  {viewMode === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 期間セレクター（ヒートマップ以外） */}
                  {(viewMode !== 'mom' || displayMode === 'chart') && (
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  )}

                  {/* 水準グラフ（折れ線） */}
                  {viewMode === 'raw' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'value', color: COLOR_VALUE, name: '韓国半導体輸出 (Billion USD)' },
                      ]}
                      yAxisFormatter={(v) => `$${v.toFixed(1)}B`}
                      tooltipValueFormatter={(v) => v != null ? `$${v.toFixed(2)}B` : 'N/A'}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
                    />
                  )}

                  {/* 前年比グラフ（折れ線） */}
                  {viewMode === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLOR_YOY, name: '韓国半導体輸出（前年比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : 'N/A'}
                      yDomain={['dataMin - 5', 'dataMax + 5']}
                      showZeroLine={true}
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {viewMode === 'mom' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'mom', color: COLOR_MOM, name: '韓国半導体輸出（前月比）' },
                      ]}
                      yAxisFormatter={(v) => `${v}%`}
                      tooltipValueFormatter={(v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : 'N/A'}
                      yDomain={['dataMin - 5', 'dataMax + 5']}
                    />
                  )}

                  {/* 前月比ヒートマップ */}
                  {viewMode === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable data={momTableData} />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="south_korean_exports" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
