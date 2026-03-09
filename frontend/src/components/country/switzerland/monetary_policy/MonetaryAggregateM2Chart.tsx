/**
 * 貨幣総量M2チャートコンポーネント
 *
 * スイス国立銀行（SNB）の貨幣総量M2の推移を表示
 * 原数値と前年比を切り替え可能
 *
 * データソース:
 * - SNB Data Portal: https://data.snb.ch/
 *
 * 発表スケジュール:
 * - 月次（Monthly）- 20日以降の最初の営業日 09:00（チューリッヒ時間）
 */
import { useMemo, useState } from 'react'
import { Button, Tooltip, Radio } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import {
  LATEST_VALUE_BOX_STYLE,
  TEXT_COLORS,
} from '../../usa/common/chartConstants'

// 型定義
import type { MonetaryAggregateM2Data } from '../../../../hooks/useDashboardData'

interface MonetaryAggregateM2ChartProps {
  data: MonetaryAggregateM2Data | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  yoy: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  value: '#4169E1', // ロイヤルブルー
  yoy: '#DC143C', // クリムゾン
}

// 表示モード
type ViewMode = 'value' | 'yoy'

export default function MonetaryAggregateM2Chart({ data }: MonetaryAggregateM2ChartProps) {
  // 表示モード（原数値 / 前年比）
  const [viewMode, setViewMode] = useState<ViewMode>('value')

  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 10,
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      value: item.value,
      yoy: item.yoy,
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2000,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].value !== null || chartData[i].yoy !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="貨幣総量M2" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="貨幣総量M2" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="monetary-aggregate-m2-chart">
      <ChartContainer
        title="貨幣総量M2"
        showPeriodSelector={false}
        dataSource="Swiss National Bank"
        sourceUrl="https://data.snb.ch/en/topics/snb"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>最新値</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>M2:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.value }}>
                {latestValue?.value ? `${(latestValue.value / 1000).toFixed(1)}B CHF` : '-'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>前年比:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.yoy }}>
                {latestValue?.yoy !== null && latestValue?.yoy !== undefined ? `${latestValue.yoy.toFixed(1)}%` : '-'}
              </span>
            </div>
            {latestValue?.date && (
              <span style={{ fontSize: 11, color: TEXT_COLORS.tertiary }}>
                ({latestValue.date})
              </span>
            )}
          </div>
          {data.next_release && (
            <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, textAlign: 'right' }}>
              次回発表: {data.next_release}
            </div>
          )}
        </div>

        {/* コントロールバー */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8, flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
            <Radio.Group
              value={viewMode}
              onChange={(e) => setViewMode(e.target.value)}
              size="small"
              optionType="button"
              buttonStyle="solid"
            >
              <Radio.Button value="value">原数値</Radio.Button>
              <Radio.Button value="yoy">前年比</Radio.Button>
            </Radio.Group>
          </div>
          <Tooltip title="比較ページを開く（貨幣総量M2）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=monetary_aggregate_m2', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        {viewMode === 'value' ? (
          <StandardLineChart
            data={filteredData}
            lines={[
              { dataKey: 'value', color: COLORS.value, name: 'M2' },
            ]}
            yAxisFormatter={(v) => `${(v / 1000).toFixed(0)}B`}
            tooltipValueFormatter={(v) => `${(v / 1000).toFixed(1)}B CHF`}
            yDomain={['dataMin - 50000', 'dataMax + 50000']}
            showZeroLine={false}
          />
        ) : (
          <StandardLineChart
            data={filteredData}
            lines={[
              { dataKey: 'yoy', color: COLORS.yoy, name: '前年比' },
            ]}
            yAxisFormatter={(v) => `${v.toFixed(0)}%`}
            tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
            yDomain={['auto', 'auto']}
            showZeroLine={true}
          />
        )}
      </ChartContainer>
    </div>
  )
}
