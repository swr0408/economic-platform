/**
 * KOF経済バロメーター チャートコンポーネント
 *
 * KOF Swiss Economic InstituteからKOF経済バロメーターデータを取得し、表示
 *
 * データ:
 * - KOF Economic Barometer（景気先行指標）
 * - 100を基準とし、100超は景気拡大、100未満は景気後退を示唆
 *
 * データソース:
 * - KOF Swiss Economic Institute
 *
 * 発表スケジュール:
 * - 毎月下旬（KOF発表）
 * - 発表時刻: 09:00 チューリッヒ時間（17:00 JST）
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
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { KofBarometerData } from '../../../../hooks/useDashboardData'

interface KofBarometerChartProps {
  data: KofBarometerData | null
}

interface ChartDataPoint {
  date: string
  value: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  kof: '#DC143C', // スイス赤
}

export default function KofBarometerChart({ data }: KofBarometerChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')

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
    }))
  }, [data])

  // データを日付昇順にソート
  const chartData = useSortedData(rawChartData)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = useMemo(() => {
    if (!chartData.length) return null
    for (let i = chartData.length - 1; i >= 0; i--) {
      if (chartData[i].value !== null) {
        return chartData[i]
      }
    }
    return null
  }, [chartData])

  if (data === null) {
    return <LoadingChart title="KOF経済バロメーター" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="KOF経済バロメーター" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="kof-barometer-chart">
      <ChartContainer
        title="KOF経済バロメーター"
        showPeriodSelector={false}
        dataSource="KOF Swiss Economic Institute"
        sourceUrl="https://kof.ethz.ch/en/forecasts-and-indicators/indicators/kof-economic-barometer.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="KOF経済バロメーター"
          value={latestValue?.value}
          date={latestValue?.date}
          format="number"
          decimals={1}
          valueColor={COLORS.kof}
          nextRelease={data.next_release}
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
                  {/* コントロールバー */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く（KOF経済バロメーター）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=kof_economic_barometer', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 期間選択 */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.kof, name: 'KOF経済バロメーター' },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}`}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                    showZeroLine={false}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="kof_economic_barometer" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
