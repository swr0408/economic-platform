/**
 * 臨時就業者数（Temporary Help Services）チャートコンポーネント
 *
 * FRED TEMPHELPS データを使用
 *
 * 表示モード:
 * - 水準（原数値）
 * - 前年比（YoY%）
 * - 前月比（MoM%）+ ヒートマップ
 *
 * 毎月第1金曜日 8:30 ET発表（BLS Employment Situation）
 *
 * 共通コンポーネントを使用
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import MarketImpactTab from '../../../indicator/MarketImpactTab'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { TemporaryHelpServicesData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  DISPLAY_MODE_OPTIONS,
  type DisplayMode,
} from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useMonthlyTableData,
} from '../common/useChartData'
import {
  LatestValueBox,
  ViewModeButtonGroup,
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
} from '../common/ChartComponents'
import { MonthlyTable } from '../common/MonthlyTable'

// =============================================================================
// 型定義
// =============================================================================

interface UsTemporaryHelpServicesChartProps {
  data: TemporaryHelpServicesData | null
}

// 指標種別
type DataKind = 'raw' | 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'raw', label: '水準' },
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]

// カラー設定
const LINE_COLOR = '#722ed1'  // 紫

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function UsTemporaryHelpServicesChart({ data }: UsTemporaryHelpServicesChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('raw')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // 指標種別毎の期間管理
  const periodKey = dataKind === 'raw' ? 'raw' : dataKind
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(periodKey, {
    raw: 10,
    yoy: 10,
    mom: 3,
  })

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data)

  // YoY / MoM を計算
  const chartData = useMemo(() => {
    if (sortedData.length === 0) return []

    return sortedData.map((item, index) => {
      // 前月比
      const prevItem = index > 0 ? sortedData[index - 1] : null
      const mom = prevItem && item.value != null && prevItem.value != null && prevItem.value !== 0
        ? Math.round(((item.value - prevItem.value) / prevItem.value) * 10000) / 100
        : null

      // 前年比（12か月前）
      const prevYearItem = index >= 12 ? sortedData[index - 12] : null
      const yoy = prevYearItem && item.value != null && prevYearItem.value != null && prevYearItem.value !== 0
        ? Math.round(((item.value - prevYearItem.value) / prevYearItem.value) * 10000) / 100
        : null

      return {
        ...item,
        yoy,
        mom,
      }
    })
  }, [sortedData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // ヒートマップ用データ
  const momTableData = useMonthlyTableData(
    chartData,
    (item: { mom: number | null }) => item.mom,
    10
  )

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="臨時就業者数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="臨時就業者数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const nextRelease = data.next_release
  const latestComputed = chartData.length > 0 ? chartData[chartData.length - 1] : null

  // 最新値表示
  const getLatestItems = () => {
    if (!latest) return []
    if (dataKind === 'raw') {
      return [
        { label: '臨時就業者数', value: latest.value, color: LINE_COLOR, format: 'number' as const, unit: 'k', decimals: 1 },
      ]
    } else if (dataKind === 'yoy') {
      return [
        { label: '前年比', value: latestComputed?.yoy != null ? `${latestComputed.yoy >= 0 ? '+' : ''}${latestComputed.yoy.toFixed(1)}%` : 'N/A', color: LINE_COLOR },
      ]
    } else {
      return [
        { label: '前月比', value: latestComputed?.mom != null ? `${latestComputed.mom >= 0 ? '+' : ''}${latestComputed.mom.toFixed(2)}%` : 'N/A', color: LINE_COLOR },
      ]
    }
  }

  return (
    <div id="temporary-help-services">
      <ChartContainer
        title="臨時就業者数（Temporary Help Services）"
        showPeriodSelector={false}
        dataSource="FRED - BLS"
        sourceUrl="https://fred.stlouisfed.org/series/TEMPHELPS"
        handbookId="temporary-help-services"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latest?.date}
          nextRelease={nextRelease}
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
                        onClick={() => window.open('/compare?s=us_temporary_help_services', '_blank')}
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

                  {/* 水準（原数値）グラフ */}
                  {dataKind === 'raw' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'value', color: LINE_COLOR, name: '臨時就業者数（千人）' },
                        ]}
                        yAxisFormatter={(v) => `${v.toLocaleString()}`}
                        yDomain={['dataMin - 50', 'dataMax + 50']}
                        showZeroLine={false}
                      />
                    </>
                  )}

                  {/* 前年比グラフ */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: LINE_COLOR, name: '臨時就業者数（前年比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 2', 'dataMax + 2']}
                        showZeroLine={true}
                      />
                    </>
                  )}

                  {/* 前月比ヒートマップ */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTable
                      data={momTableData}
                      helperText="※ 臨時就業者数 前月比（単位: %）"
                    />
                  )}

                  {/* 前月比チャート */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          { dataKey: 'mom', color: LINE_COLOR, name: '臨時就業者数（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="unemployment_rate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
