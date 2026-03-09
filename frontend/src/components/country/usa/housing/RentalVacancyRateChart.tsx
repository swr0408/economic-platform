/**
 * 賃貸空室率チャートコンポーネント
 *
 * FREDから取得した賃貸空室率（RRVRUSQ156N）を表示
 * データソース: FRED (Census Bureau Housing Vacancies and Homeownership)
 *
 * タブ切り替え:
 * - 時系列: 現数値グラフのみ（四半期データ）
 * - マーケットインパクト: 発表時の市場への影響分析
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { RentalVacancyRateData } from '../../../../hooks/useDashboardData'
import type { PeriodValue } from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface RentalVacancyRateChartProps {
  rentalVacancyRateData: RentalVacancyRateData | null
}

// カラー設定
const COLORS = {
  value: '#8b5cf6',  // パープル（現数値）
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function RentalVacancyRateChart({ rentalVacancyRateData }: RentalVacancyRateChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(20)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // データを日付昇順にソート
  const chartData = useSortedData(rentalVacancyRateData?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  const hasData = chartData.length > 0

  // ローディング状態
  if (rentalVacancyRateData === null) {
    return <LoadingChart title="賃貸空室率 (RRVRUSQ156N)" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="賃貸空室率 (RRVRUSQ156N)" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = rentalVacancyRateData.latest

  return (
    <div id="rental-vacancy-rate">
      <ChartContainer
        title="賃貸空室率"
        showPeriodSelector={false}
        dataSource="Census Bureau"
        sourceUrl="https://www.census.gov/housing/hvs/index.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          value={latest?.value}
          valueColor={COLORS.value}
          date={latest?.date}
          format="percent"
          decimals={1}
        />
        {/* 四半期データのため、次回発表日は不定期 */}
        {rentalVacancyRateData?.next_release && (
          <div style={{ fontSize: 11, color: '#8c8c8c', textAlign: 'right', marginTop: 4 }}>
            {rentalVacancyRateData.next_release.note}
          </div>
        )}

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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く（賃貸空室率）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=rental_vacancy_rate', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* チャート表示 */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLORS.value, name: '賃貸空室率', hide: hiddenSeries.has('value') },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                    onLegendClick={handleLegendClick}
                    showZeroLine={false}
                    showFiftyLine={false}
                    yDomain={['dataMin - 1', 'dataMax + 1']}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="rental_vacancy_rate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
