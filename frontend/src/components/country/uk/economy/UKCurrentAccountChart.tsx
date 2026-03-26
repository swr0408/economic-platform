/**
 * UK経常収支チャートコンポーネント
 *
 * Current Account Balance, BOP, Current Prices, SA
 * シリーズ: HBOP (ONS PNBP Dataset)
 *
 * データソース:
 * - Office for National Statistics (ONS)
 *
 * 発表スケジュール:
 * - 四半期
 *
 * 単位:
 * - £ billions（十億ポンド）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useQuarterlyTableData,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { UKCurrentAccountData } from '../../../../hooks/useDashboardData'

interface UKCurrentAccountChartProps {
  data: UKCurrentAccountData | null
}

interface ChartDataPoint {
  date: string
  value: number
  qoq_change: number | null
  [key: string]: unknown
}

type DataKind = 'value' | 'qoq'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'value', label: '現数値' },
  { mode: 'qoq', label: '前期比' },
]

type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

const COLORS = {
  value: '#1890ff',
  qoq: '#52c41a',
}

export default function UKCurrentAccountChart({ data }: UKCurrentAccountChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 20,
    qoq: 20,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    // QoQ changeをMapに
    const qoqMap = new Map<string, number>()
    if (data.qoq_change) {
      data.qoq_change.forEach(item => {
        qoqMap.set(item.date, item.value)
      })
    }

    return data.data
      .map(item => ({
        date: item.date,
        value: item.value,
        qoq_change: qoqMap.get(item.date) ?? null,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（四半期別マトリックス）
  const qoqTableData = useQuarterlyTableData(
    chartData,
    (item) => item.qoq_change,
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  // 現在の表示値
  const currentValue = useMemo(() => {
    if (!latest) return null
    return dataKind === 'value' ? latest.value : latest.qoq_change
  }, [latest, dataKind])

  const currentColor = dataKind === 'value' ? COLORS.value : COLORS.qoq

  if (data === null) {
    return <LoadingChart title="経常収支（イギリス）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="経常収支（イギリス）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="uk-current-account-chart">
      <ChartContainer
        title="経常収支"
        showPeriodSelector={false}
        dataSource="ONS"
        sourceUrl="https://www.ons.gov.uk/economy/nationalaccounts/balanceofpayments/timeseries/hbop/pnbp"
        handbookId="current-account"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={dataKind === 'value' ? '経常収支' : '前期増減幅'}
          value={currentValue != null ? `£${currentValue >= 0 ? '+' : ''}${currentValue.toFixed(2)}bn` : null}
          valueColor={currentColor}
          date={latest?.date}
          nextRelease={data.next_release ?? undefined}
          format="raw"
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
                        onClick={() => window.open('/compare?s=uk_current_account', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（前期比のときのみ） */}
                  {dataKind === 'qoq' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* テーブル表示 */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && (
                    <QuarterlyTable
                      data={qoqTableData}
                      decimals={2}
                      showLegend={false}
                      helperText="※ 直近10年間の前期増減幅データ（単位: £bn）"
                    />
                  )}

                  {/* 期間セレクター + グラフ */}
                  {!(dataKind === 'qoq' && displayMode === 'heatmap') && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                      {dataKind === 'value' && (
                        <StandardBarChart
                          data={filteredData}
                          bars={[
                            {
                              dataKey: 'value',
                              color: COLORS.value,
                              name: '経常収支（£bn）',
                            },
                          ]}
                          yAxisFormatter={(v) => `${v}`}
                          tooltipValueFormatter={(v) => `£${v >= 0 ? '+' : ''}${v.toFixed(2)}bn`}
                        />
                      )}

                      {dataKind === 'qoq' && displayMode === 'chart' && (
                        <StandardBarChart
                          data={filteredData}
                          bars={[
                            {
                              dataKey: 'qoq_change',
                              color: COLORS.qoq,
                              name: '前期増減幅（£bn）',
                            },
                          ]}
                          yAxisFormatter={(v) => `${v}`}
                          tooltipValueFormatter={(v) => `£${v >= 0 ? '+' : ''}${v.toFixed(2)}bn`}
                        />
                      )}
                    </>
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="uk_current_account" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
