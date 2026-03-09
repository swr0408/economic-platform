/**
 * ハリファックス住宅価格指数チャートコンポーネント
 *
 * データ:
 * - ハリファックス住宅価格指数 前月比（MoM）
 * - ハリファックス住宅価格指数 前年比（YoY）
 *
 * 表示モード:
 * - MoM テーブル: 前月比の月別テーブル
 * - MoM チャート: 前月比の棒グラフ
 * - YoY: 前年比の折れ線グラフ
 *
 * データソース:
 * - DB: economic_calendar_events（CSV蓄積データ）
 * - PDF: https://www.halifax.co.uk/media-centre/house-price-index.html
 *
 * 発表スケジュール:
 * - 月次（不定期・Halifaxサイトから取得）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip as AntTooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

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
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'

import type { HalifaxHousePriceData } from '../../../../hooks/useDashboardData'

interface HalifaxHousePriceChartProps {
  data: HalifaxHousePriceData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
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

// グラフの色
const COLORS = {
  mom: '#e74c3c', // 赤
  yoy: '#3498db', // 青
}

// 系列名
const SERIES_NAMES = {
  mom: 'ハリファックス住宅価格指数（前月比）',
  yoy: 'ハリファックス住宅価格指数（前年比）',
}

export default function HalifaxHousePriceChart({ data }: HalifaxHousePriceChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('yoy')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    mom: 3,
  })

  // propsのデータをチャート用に変換
  const rawMoMData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.mom) return []
    return data.mom.map(point => ({
      date: point.date,
      value: point.value,
    }))
  }, [data])

  const rawYoYData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.yoy) return []
    return data.yoy.map(point => ({
      date: point.date,
      value: point.value,
    }))
  }, [data])

  // データを日付昇順にソート
  const momChartData = useSortedData(rawMoMData)
  const yoyChartData = useSortedData(rawYoYData)

  // 期間フィルタリング
  const filteredMoMData = usePeriodFiltering(momChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const filteredYoYData = usePeriodFiltering(yoyChartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // 前月比テーブル用データ
  const momTableData = useMonthlyTableData(
    momChartData,
    (item) => item.value,
    10
  )

  const hasMoMData = momChartData.length > 0
  const hasYoYData = yoyChartData.length > 0
  const hasData = hasMoMData || hasYoYData

  // 最新値を取得
  const latestMoM = data?.latest_mom
  const latestYoY = data?.latest_yoy
  // nextReleaseはstring形式で返ってくるのでオブジェクト形式に変換
  const nextRelease = data?.next_release ? { date: data.next_release } : null

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="ハリファックス住宅価格指数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="ハリファックス住宅価格指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値の表示用アイテム
  const getLatestItems = () => {
    const items = []

    if (latestMoM?.value !== null && latestMoM?.value !== undefined) {
      items.push({
        label: '前月比',
        value: `${latestMoM.value >= 0 ? '+' : ''}${latestMoM.value.toFixed(1)}%`,
        color: latestMoM.value >= 0 ? '#f5222d' : '#52c41a',
      })
    }

    if (latestYoY?.value !== null && latestYoY?.value !== undefined) {
      items.push({
        label: '前年比',
        value: `${latestYoY.value >= 0 ? '+' : ''}${latestYoY.value.toFixed(1)}%`,
        color: latestYoY.value >= 0 ? '#f5222d' : '#52c41a',
      })
    }

    return items
  }

  // データ比較ページを開く
  const handleCompare = () => {
    const series = dataKind === 'yoy' ? 'uk_halifax_house_price_yoy' : 'uk_halifax_house_price_mom'
    window.open(`/compare?s=${series}`, '_blank')
  }

  return (
    <div id="uk-halifax-house-price-chart">
      <ChartContainer
        title="ハリファックス住宅価格指数"
        showPeriodSelector={false}
        dataSource="Halifax"
        sourceUrl="https://www.halifax.co.uk/media-centre/house-price-index.html"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={getLatestItems()}
          date={latestMoM?.date || latestYoY?.date}
          nextRelease={nextRelease}
        />

        {/* 上段: 指標種別 + データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
          <AntTooltip title="比較ページを開く">
            <Button icon={<AreaChartOutlined />} onClick={handleCompare}>データ比較</Button>
          </AntTooltip>
        </div>

        {/* 下段: 表示形式（前月比のときのみ） */}
        {dataKind === 'mom' && (
          <div style={{ marginBottom: 8 }}>
            <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
          </div>
        )}

        {/* MoMテーブル */}
        {dataKind === 'mom' && displayMode === 'heatmap' && hasMoMData && (
          <MonthlyTable
            data={momTableData}
            decimals={1}
            helperText="※ 直近10年間の前月比データ（単位: %）"
          />
        )}

        {/* MoM棒グラフ */}
        {dataKind === 'mom' && displayMode === 'chart' && hasMoMData && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardBarChart
              data={filteredMoMData}
              bars={[
                {
                  dataKey: 'value',
                  color: COLORS.mom,
                  name: SERIES_NAMES.mom,
                },
              ]}
              yAxisFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
              tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
              tooltipLabelFormatter={formatDateLabelJP}
              yDomain={['dataMin - 1', 'dataMax + 1']}
              showZeroLine
            />
          </>
        )}

        {/* YoY折れ線グラフ */}
        {dataKind === 'yoy' && hasYoYData && (
          <>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <StandardLineChart
              data={filteredYoYData}
              lines={[
                {
                  dataKey: 'value',
                  color: COLORS.yoy,
                  name: SERIES_NAMES.yoy,
                },
              ]}
              xAxisFormatter={formatDateLabel}
              yAxisFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
              tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
              tooltipLabelFormatter={formatDateLabelJP}
              yDomain={['dataMin - 2', 'dataMax + 2']}
              showZeroLine
            />
          </>
        )}

        {/* データなし */}
        {dataKind === 'mom' && !hasMoMData && <NoDataMessage />}
        {dataKind === 'yoy' && !hasYoYData && <NoDataMessage />}
      </ChartContainer>
    </div>
  )
}
