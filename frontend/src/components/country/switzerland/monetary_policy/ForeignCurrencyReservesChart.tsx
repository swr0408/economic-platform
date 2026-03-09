/**
 * 外貨準備チャートコンポーネント
 *
 * スイス国立銀行（SNB）の外貨準備の推移を表示（CHFとUSD）
 *
 * データソース:
 * - SNB Data Portal: https://data.snb.ch/
 *
 * 発表スケジュール:
 * - 不定期（月次程度で更新）
 */
import { useMemo } from 'react'
import { Button, Tooltip } from 'antd'
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
import type { ForeignCurrencyReservesData } from '../../../../hooks/useDashboardData'

interface ForeignCurrencyReservesChartProps {
  data: ForeignCurrencyReservesData | null
}

interface ChartDataPoint {
  date: string
  chf: number | null
  usd: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  chf: '#DC143C', // スイスカラー（クリムゾン）
  usd: '#228B22', // ドルカラー（グリーン）
}

export default function ForeignCurrencyReservesChart({ data }: ForeignCurrencyReservesChartProps) {
  // ビューモード毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement('default', {
    default: 10,
  })

  // propsのデータをチャート用に変換
  const rawChartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    return data.data.map((item) => ({
      date: item.date,
      chf: item.chf,
      usd: item.usd,
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
      if (chartData[i].chf !== null || chartData[i].usd !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="外貨準備" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="外貨準備" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="foreign-currency-reserves-chart">
      <ChartContainer
        title="外貨準備"
        showPeriodSelector={false}
        dataSource="Swiss National Bank"
        sourceUrl="https://data.snb.ch/en/topics/snb"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: TEXT_COLORS.secondary, fontWeight: 'bold' }}>最新値</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>CHF:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.chf }}>
                {latestValue?.chf ? `${(latestValue.chf / 1000).toFixed(1)}B` : '-'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>USD:</span>
              <span style={{ fontSize: 16, fontWeight: 'bold', color: COLORS.usd }}>
                {latestValue?.usd ? `${(latestValue.usd / 1000).toFixed(1)}B` : '-'}
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, marginTop: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く（外貨準備CHF）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=foreign_currency_reserves_chf', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* グラフ */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'chf', color: COLORS.chf, name: 'CHF' },
            { dataKey: 'usd', color: COLORS.usd, name: 'USD' },
          ]}
          yAxisFormatter={(v) => `${(v / 1000).toFixed(0)}B`}
          tooltipValueFormatter={(v, name) => `${(v / 1000).toFixed(1)}B ${name === 'chf' ? 'CHF' : 'USD'}`}
          yDomain={['dataMin - 50000', 'dataMax + 50000']}
          showZeroLine={false}
        />
      </ChartContainer>
    </div>
  )
}
