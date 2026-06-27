/**
 * フィラデルフィア連銀製造業景気指数チャートコンポーネント
 *
 * 共通モジュールを使用してリファクタリング済み
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip, Switch } from 'antd'
import { AreaChartOutlined, InfoCircleOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PhiladelphiaFedData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  formatDateLabel,
  useHiddenSeries,
  createNumberFormatter,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../common/ChartComponents'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// =============================================================================
// 型定義
// =============================================================================

interface PhiladelphiaFedChartProps {
  data: PhiladelphiaFedData | null
}

// シリーズ設定（10シリーズ）
const SERIES_CONFIG = {
  general_activity_current: { name: '一般活動', color: '#0958D9', strokeWidth: 2 },
  general_activity_future: { name: '一般活動期待', color: '#91CAFF', strokeWidth: 2 },
  new_orders_current: { name: '新規受注', color: '#389e0d', strokeWidth: 2 },
  new_orders_future: { name: '新規受注期待', color: '#b7eb8f', strokeWidth: 2 },
  prices_paid_current: { name: '投入価格', color: '#cf1322', strokeWidth: 2 },
  prices_paid_future: { name: '投入価格期待', color: '#ffa39e', strokeWidth: 2 },
  employment_current: { name: '雇用', color: '#d46b08', strokeWidth: 2 },
  employment_future: { name: '雇用期待', color: '#ffd591', strokeWidth: 2 },
  // 製造業BOSには「現況設備投資」設問が無いため、この系列のみ非製造業景況調査
  // (NMBOS, FRED: CEBNDIF066MSFRBPHI) 由来。発表が製造業より約1週間遅れる。
  // 専用トグル（下記 showNonmfgCapex）でのみ表示制御する。
  capex_current: { name: '設備投資・ソフト/機械設備（非製造業・現況）', color: '#9346ff', strokeWidth: 2 },
  capex_future: { name: '設備投資期待', color: '#d3adf7', strokeWidth: 2 },
}

// 専用トグルで制御する非製造業由来の系列キー
const NONMFG_CAPEX_KEY = 'capex_current'

// 初期非表示シリーズ（一般活動指数のみ表示）
// capex_current は専用トグルで lines への含有自体を制御するためここには含めない
const INITIAL_HIDDEN_SERIES = new Set([
  'general_activity_future',
  'new_orders_current',
  'new_orders_future',
  'prices_paid_current',
  'prices_paid_future',
  'employment_current',
  'employment_future',
  'capex_future',
])

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function PhiladelphiaFedChart({ data }: PhiladelphiaFedChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  // 非製造業由来の現況設備投資を表示するか（既定OFF）
  const [showNonmfgCapex, setShowNonmfgCapex] = useState<boolean>(false)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries(INITIAL_HIDDEN_SERIES)

  // データを日付昇順にソート
  const chartData = useMemo(() => {
    if (!data?.data || data.data.length === 0) return []

    return [...data.data]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map((item) => ({
        date: item.date,
        general_activity_current: item.general_activity_current,
        general_activity_future: item.general_activity_future,
        new_orders_current: item.new_orders_current,
        new_orders_future: item.new_orders_future,
        prices_paid_current: item.prices_paid_current,
        prices_paid_future: item.prices_paid_future,
        employment_current: item.employment_current,
        employment_future: item.employment_future,
        capex_current: item.capex_current,
        capex_future: item.capex_future,
      }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="フィラデルフィア連銀製造業景気指数" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="フィラデルフィア連銀製造業景気指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を取得
  const latestData = data.latest

  // StandardLineChart用のlines配列を生成
  // 非製造業由来の現況設備投資は専用トグルがONのときのみ含める
  const lines = Object.entries(SERIES_CONFIG)
    .filter(([key]) => key !== NONMFG_CAPEX_KEY || showNonmfgCapex)
    .map(([key, config]) => ({
      dataKey: key,
      color: config.color,
      name: config.name,
      hide: hiddenSeries.has(key),
      strokeWidth: config.strokeWidth,
    }))

  return (
    <div id="philadelphia-fed-chart">
      <ChartContainer
        title="フィラデルフィア連銀製造業景気指数 現況 / 期待（今後6か月）"
        showPeriodSelector={false}
        dataSource="Federal Reserve Bank of Philadelphia / FRED"
        sourceUrl="https://www.philadelphiafed.org/surveys-and-data/regional-economic-analysis/manufacturing-business-outlook-survey"
      >
        {/* 最新値表示 */}
        {latestData && (
          <LatestValueBox
            items={[
              { label: '一般活動', value: latestData.general_activity_current, format: 'number', decimals: 1, color: SERIES_CONFIG.general_activity_current.color },
              { label: '期待指数', value: latestData.general_activity_future, format: 'number', decimals: 1, color: SERIES_CONFIG.general_activity_future.color },
            ]}
            date={latestData.date}
            nextRelease={data.next_release}
          />
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Switch
                          size="small"
                          checked={showNonmfgCapex}
                          onChange={setShowNonmfgCapex}
                        />
                        <span style={{ fontSize: 12, color: '#595959' }}>設備投資・ソフト/機械設備（非製造業・現況）</span>
                        <Tooltip
                          title="内容は「機械設備・ソフトウェア」の現況設備投資です（前月比の拡散指数）。ただしこの系列のみ非製造業景況調査（NMBOS, FRED: CEBNDIF066MSFRBPHI, 対象=サービス業）由来です。製造業調査には現況設備投資の設問が無いため代替表示しています。発表が製造業より約1週間遅く（第4火曜）、最新月は遅れて反映されます。"
                        >
                          <InfoCircleOutlined style={{ fontSize: 12, color: '#8c8c8c' }} />
                        </Tooltip>
                      </div>
                      <Tooltip title="比較ページを開く">
                        <Button
                          icon={<AreaChartOutlined />}
                          onClick={() => window.open('/compare?s=philadelphia_fed', '_blank')}
                        >
                          データ比較
                        </Button>
                      </Tooltip>
                    </div>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={lines}
                    yDomain={['dataMin - 5', 'dataMax + 5']}
                    yAxisFormatter={(v) => v.toFixed(0)}
                    tooltipLabelFormatter={formatDateLabel}
                    tooltipFormatter={createNumberFormatter(1)}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="philadelphia_fed" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
