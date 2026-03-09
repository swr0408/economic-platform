/**
 * Japan Tokyo CPI Chart Component
 * 東京都区部消費者物価指数チャート（速報）
 *
 * 東京CPIは全国CPIに先行して発表される速報的な指標
 *
 * データ項目:
 * - yoy: 前年同月比 (%)
 * - mom: 前月比 (%)
 * - core_yoy/mom: コア（生鮮食品除く）
 * - core_core_yoy/mom: コアコア（食料・エネルギー除く）
 */

import { useEffect, useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import {
  CHART_COLORS,
} from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
  useHiddenSeries,
  useMultiValueMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ViewModeButtonGroup,
  DataTypeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTableWithDataTypes } from '../../usa/common/MonthlyTable'

import {
  fetchTokyoCPIData,
  type CPIResponse,
  type CPIDataPoint,
} from '../../../../utils/japan/cpiApi'

// =============================================================================
// 型定義
// =============================================================================

interface ChartDataPoint {
  date: string
  yoy: number | null
  mom: number | null
  core_yoy: number | null
  core_mom: number | null
  core_core_yoy: number | null
  core_core_mom: number | null
}

type DataKind = 'yoy' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'mom', label: '前月比' },
]
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

// CPIデータタイプ
type CPIDataType = 'all' | 'core' | 'core_core'

// CPIデータタイプ設定
const CPI_DATA_TYPE_OPTIONS: { type: CPIDataType; label: string }[] = [
  { type: 'all', label: '総合' },
  { type: 'core', label: 'コア' },
  { type: 'core_core', label: 'コアコア' },
]

// カラー設定（東京CPIはオレンジベース）
const COLORS = {
  all_yoy: CHART_COLORS.orange,
  all_mom: CHART_COLORS.orange,
  core_yoy: CHART_COLORS.positive,
  core_mom: CHART_COLORS.positive,
  core_core_yoy: CHART_COLORS.purple,
  core_core_mom: CHART_COLORS.purple,
}

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}`
}

const formatDateLabelJP = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return `${date.getFullYear()}年${date.getMonth() + 1}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function TokyoCPIChart() {
  const [data, setData] = useState<CPIResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [dataType, setDataType] = useState<CPIDataType>('all')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  // データ取得
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchTokyoCPIData()
        if (res.error) {
          setError(res.error)
        } else {
          setData(res)
        }
      } catch (err) {
        console.error('Error loading Tokyo CPI data:', err)
        setError('データの読み込みに失敗しました')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  // データを変換
  const chartData = useMemo(() => {
    if (!data?.data) return []

    return data.data
      .filter((d: CPIDataPoint) => d.yoy !== null || d.mom !== null)
      .map((d: CPIDataPoint) => ({
        date: d.date,
        yoy: d.yoy,
        mom: d.mom,
        core_yoy: d.core_yoy,
        core_mom: d.core_mom,
        core_core_yoy: d.core_core_yoy,
        core_core_mom: d.core_core_mom,
      }))
  }, [data])

  // データを日付昇順にソート
  const sortedData = useSortedData(chartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ
  const momTableData = useMultiValueMonthlyTableData(
    sortedData,
    {
      all: (item: ChartDataPoint) => item.mom,
      core: (item: ChartDataPoint) => item.core_mom,
      core_core: (item: ChartDataPoint) => item.core_core_mom,
    },
    10
  )

  const hasData = sortedData.length > 0

  // ローディング状態
  if (loading) {
    return <LoadingChart title="東京都区部消費者物価指数（CPI）" />
  }

  // エラー状態
  if (error) {
    return (
      <ChartContainer title="東京都区部消費者物価指数（CPI）" showPeriodSelector={false} showDataSource={false}>
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff4d4f' }}>{error}</div>
      </ChartContainer>
    )
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="東京都区部消費者物価指数（CPI）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data?.latest

  // 次回発表日のフォーマット
  const formatNextRelease = () => {
    if (!data?.next_release) return null
    const nr = data.next_release
    if (nr.datetime_jst) {
      const dt = new Date(nr.datetime_jst)
      return `${dt.getMonth() + 1}/${dt.getDate()} ${dt.getHours().toString().padStart(2, '0')}:${dt.getMinutes().toString().padStart(2, '0')}`
    }
    if (nr.date) {
      const dt = new Date(nr.date)
      return `${dt.getMonth() + 1}/${dt.getDate()}${nr.time_jst ? ` ${nr.time_jst}` : ''}`
    }
    return null
  }

  return (
    <div id="japan-tokyo-cpi-chart">
      <ChartContainer
        title="東京都区部消費者物価指数（CPI）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="総務省統計局"
        sourceUrl="https://www.stat.go.jp/data/cpi/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '総合',
              value: dataKind === 'yoy' ? latest?.yoy : latest?.mom,
              color: COLORS.all_yoy,
              format: 'percent',
            },
            {
              label: 'コア',
              value: dataKind === 'yoy' ? latest?.core_yoy : latest?.core_mom,
              color: COLORS.core_yoy,
              format: 'percent',
            },
            {
              label: 'コアコア',
              value: dataKind === 'yoy' ? latest?.core_core_yoy : latest?.core_core_mom,
              color: COLORS.core_core_yoy,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatDateLabelJP}
          nextRelease={data?.next_release ? { date: formatNextRelease() || '' } : undefined}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=japan_tokyo_cpi_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {dataKind === 'mom' && (
                    <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                  )}

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardLineChart
                        data={filteredData}
                        lines={[
                          { dataKey: 'yoy', color: COLORS.all_yoy, name: '総合（前年比）', hide: hiddenSeries.has('yoy') },
                          { dataKey: 'core_yoy', color: COLORS.core_yoy, name: 'コア（前年比）', hide: hiddenSeries.has('core_yoy') },
                          { dataKey: 'core_core_yoy', color: COLORS.core_core_yoy, name: 'コアコア（前年比）', hide: hiddenSeries.has('core_core_yoy') },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 1', 'dataMax + 1']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                        onLegendClick={handleLegendClick}
                      />
                    </>
                  )}

                  {/* 前月比テーブル */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && (
                    <MonthlyTableWithDataTypes
                      data={momTableData}
                      dataTypes={CPI_DATA_TYPE_OPTIONS}
                      selectedType={dataType}
                      onTypeChange={setDataType}
                      decimals={1}
                    />
                  )}

                  {/* 前月比グラフ（棒グラフ） */}
                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <>
                      <DataTypeButtonGroup options={CPI_DATA_TYPE_OPTIONS} currentType={dataType} onChange={setDataType} />
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <StandardBarChart
                        data={filteredData}
                        bars={[
                          dataType === 'all'
                            ? { dataKey: 'mom', color: COLORS.all_mom, name: '総合（前月比）' }
                            : dataType === 'core'
                            ? { dataKey: 'core_mom', color: COLORS.core_mom, name: 'コア（前月比）' }
                            : { dataKey: 'core_core_mom', color: COLORS.core_core_mom, name: 'コアコア（前月比）' },
                        ]}
                        yAxisFormatter={(v) => `${v}%`}
                        yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                        xAxisFormatter={formatDateLabel}
                        tooltipLabelFormatter={formatDateLabelJP}
                        tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                      />
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="jp_tokyo_cpi" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
