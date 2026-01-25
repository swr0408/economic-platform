/**
 * Trimmed Mean PCE Inflation Rate チャートコンポーネント
 *
 * Dallas Fed から取得した Trimmed Mean PCE データを表示
 * - 1-month: 1ヶ月変化率（年率換算）
 * - 6-month: 6ヶ月変化率（年率換算）
 * - 12-month: 12ヶ月変化率
 *
 * データソース: Dallas Fed
 * https://www.dallasfed.org/research/pce
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip, Radio } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { TrimmedMeanPCEData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { CHART_COLORS } from '../common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../common/ChartComponents'

// =============================================================================
// 型定義
// =============================================================================

interface TrimmedMeanPCEChartProps {
  data: TrimmedMeanPCEData | null
}

// シリーズタイプ
type SeriesType = 'one_month' | 'six_month' | 'twelve_month'

// シリーズ設定
const SERIES_CONFIG: Record<SeriesType, { label: string; name: string; color: string }> = {
  one_month: {
    label: '1ヶ月年率',
    name: 'Trimmed Mean PCE（1ヶ月年率）',
    color: CHART_COLORS.primary,
  },
  six_month: {
    label: '6ヶ月年率',
    name: 'Trimmed Mean PCE（6ヶ月年率）',
    color: CHART_COLORS.orange,
  },
  twelve_month: {
    label: '12ヶ月変化率',
    name: 'Trimmed Mean PCE（12ヶ月変化率）',
    color: CHART_COLORS.purple,
  },
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function TrimmedMeanPCEChart({ data }: TrimmedMeanPCEChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [selectedSeries, setSelectedSeries] = useState<SeriesType>('twelve_month')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを日付昇順にソート
  const sortedData = useSortedData(data?.data)

  // チャート用データに変換
  const chartData = useMemo(() => {
    return sortedData.map((item) => ({
      date: item.date,
      one_month: item.one_month,
      six_month: item.six_month,
      twelve_month: item.twelve_month,
    }))
  }, [sortedData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  // ローディング状態
  if (data === null) {
    return <LoadingChart title="Trimmed Mean PCE Inflation Rate" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="Trimmed Mean PCE Inflation Rate" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest
  const currentConfig = SERIES_CONFIG[selectedSeries]

  return (
    <div id="trimmed-mean-pce">
      <ChartContainer
        title="Trimmed Mean PCE Inflation Rate"
        showPeriodSelector={false}
        dataSource="Dallas Fed"
        sourceUrl="https://www.dallasfed.org/research/pce"
      >
        {/* シリーズ切り替えボタン */}
        <div style={{ marginBottom: 16 }}>
          <Radio.Group
            value={selectedSeries}
            onChange={(e) => setSelectedSeries(e.target.value)}
            buttonStyle="solid"
            size="middle"
          >
            <Radio.Button value="twelve_month">12ヶ月変化率</Radio.Button>
            <Radio.Button value="six_month">6ヶ月年率</Radio.Button>
            <Radio.Button value="one_month">1ヶ月年率</Radio.Button>
          </Radio.Group>
        </div>

        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '12ヶ月変化率',
              value: latest?.twelve_month,
              color: SERIES_CONFIG.twelve_month.color,
              format: 'percent',
            },
            {
              label: '6ヶ月年率',
              value: latest?.six_month,
              color: SERIES_CONFIG.six_month.color,
              format: 'percent',
            },
            {
              label: '1ヶ月年率',
              value: latest?.one_month,
              color: SERIES_CONFIG.one_month.color,
              format: 'percent',
            },
          ]}
          date={latest?.date}
          nextRelease={data.next_release}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=trimmed_mean_pce_12m&s=us_core_pce_deflator_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* チャート表示 */}
        <StandardLineChart
          data={filteredData}
          lines={[
            {
              dataKey: selectedSeries,
              color: currentConfig.color,
              name: currentConfig.name,
              hide: hiddenSeries.has(selectedSeries),
            },
          ]}
          yAxisFormatter={(v) => `${v}%`}
          yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}
