/**
 * カナダ対米輸出依存度チャートコンポーネント
 *
 * 対米輸出依存度（米国向け輸出/総輸出）の推移を表示
 *
 * データソース:
 * - Statistics Canada Table 12-10-0011-01
 * - International merchandise trade for all countries and by Principal Trading Partners
 *
 * 発表スケジュール:
 * - 月次（対象月の約2ヶ月後）
 * - 発表時刻: 08:30 ET
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { CaUsExportDependenceData } from '../../../../hooks/useDashboardData'

interface CaUsExportDependenceChartProps {
  data: CaUsExportDependenceData | null
}

type ViewMode = 'raw' | 'ma_3m' | 'ma_12m'

interface ChartDataItem {
  date: string
  value: number
  rawValue?: number
  us_export?: number
  total_export?: number
  ma_3m?: number
  ma_12m?: number
  [key: string]: string | number | boolean | null | undefined
}

export default function CaUsExportDependenceChart({ data }: CaUsExportDependenceChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('raw')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(viewMode, {
    raw: 'default' as PeriodType,
    ma_3m: 'default' as PeriodType,
    ma_12m: 'default' as PeriodType,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: ChartDataItem[] = data.data.map((item) => {
      let value = 0
      switch (viewMode) {
        case 'raw':
          value = item.value ?? 0
          break
        case 'ma_3m':
          value = item.ma_3m ?? 0
          break
        case 'ma_12m':
          value = item.ma_12m ?? 0
          break
      }
      return {
        date: item.date,
        value,
        rawValue: item.value,
        us_export: item.us_export,
        total_export: item.total_export,
        ma_3m: item.ma_3m,
        ma_12m: item.ma_12m,
      }
    })

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data, viewMode])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="対米輸出依存度" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="対米輸出依存度" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const viewModeOptions = [
    { mode: 'raw' as ViewMode, label: '単月' },
    { mode: 'ma_3m' as ViewMode, label: '3ヶ月移動平均' },
    { mode: 'ma_12m' as ViewMode, label: '12ヶ月移動平均' },
  ]

  // 表示ラベルを取得
  const getViewModeLabel = (mode: ViewMode) => {
    switch (mode) {
      case 'raw': return '対米輸出依存度'
      case 'ma_3m': return '対米輸出依存度（3MMA）'
      case 'ma_12m': return '対米輸出依存度（12MMA）'
    }
  }

  // 最新値を取得（ViewModeに応じて）
  const getLatestValue = () => {
    if (!latestValue) return undefined
    switch (viewMode) {
      case 'raw':
        return latestValue.value
      case 'ma_3m':
        return latestValue.ma_3m
      case 'ma_12m':
        return latestValue.ma_12m
    }
  }

  // 比較ページ用のキーを取得
  const getCompareKey = () => {
    switch (viewMode) {
      case 'raw':
        return 'raw'
      case 'ma_3m':
        return 'ma_3m'
      case 'ma_12m':
        return 'ma_12m'
    }
  }

  return (
    <div id="ca-us-export-dependence-chart">
      <ChartContainer
        title="対米輸出依存度"
        showPeriodSelector={false}
        dataSource="Statistics Canada"
        sourceUrl="https://www.statcan.gc.ca/en/subjects-start/international_trade"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getViewModeLabel(viewMode)}
          value={getLatestValue()}
          valueColor={CHART_COLORS.primary}
          date={latestValue?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format="percent"
          decimals={1}
        />

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
                    <ViewModeButtonGroup
                      options={viewModeOptions}
                      currentMode={viewMode}
                      onChange={setViewMode}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(`/compare?s=ca_us_export_dependence_${getCompareKey()}`, '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  <ZoomableChart
                    data={filteredData}
                    dataKey="value"
                    name={getViewModeLabel(viewMode)}
                    color={CHART_COLORS.primary}
                    height={450}
                    tickFormatter={(v: number) => `${v.toFixed(0)}%`}
                    tooltipFormatter={(v: number) => `${v.toFixed(1)}%`}
                    showZeroLine={false}
                    domain={[60, 85]}
                  />
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="canada_international_merchandise_trade" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
