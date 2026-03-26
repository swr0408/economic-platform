/**
 * スイス貿易収支チャートコンポーネント
 *
 * SNB Data Portal: ausshalam cube (Foreign trade by country, monthly)
 * Total 2（金・貴金属含む）- 6地域合計
 *
 * データソース:
 * - Swiss National Bank (SNB Data Portal)
 *
 * 発表スケジュール:
 * - 月次
 *
 * 単位:
 * - B CHF（十億スイスフラン）
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
  useMonthlyTableData,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { MonthlyTable } from '../../usa/common/MonthlyTable'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CHBalanceOfTradeData } from '../../../../hooks/useDashboardData'

interface CHBalanceOfTradeChartProps {
  data: CHBalanceOfTradeData | null
}

interface ChartDataPoint {
  date: string
  value: number
  mom_change: number | null
  [key: string]: unknown
}

// 指標種別
type DataKind = 'value' | 'mom'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'value', label: '原数値' },
  { mode: 'mom', label: '前月増減幅' },
]
type DisplayMode = 'chart' | 'heatmap'
const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

const COLORS = {
  value: '#1890ff',
  mom: '#52c41a',
}

export default function CHBalanceOfTradeChart({ data }: CHBalanceOfTradeChartProps) {
  const [dataKind, setDataKind] = useState<DataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  // データ種別毎の期間管理
  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 20,
    mom: 3,
  })

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    // MoM changeをMapに
    const momMap = new Map<string, number>()
    if (data.mom_change) {
      data.mom_change.forEach(item => {
        momMap.set(item.date, item.value)
      })
    }

    return data.data
      .map(item => ({
        date: item.date,
        value: item.value,
        mom_change: momMap.get(item.date) ?? null,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  // テーブル用データ（年別×月別のマトリックス）
  const tableData = useMonthlyTableData(chartData, (item) =>
    dataKind === 'mom' ? item.mom_change : item.value
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
    return dataKind === 'value' ? latest.value : latest.mom_change
  }, [latest, dataKind])

  const currentColor = dataKind === 'value' ? COLORS.value : COLORS.mom

  if (data === null) {
    return <LoadingChart title="貿易収支（スイス）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="貿易収支（スイス）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ch-balance-of-trade-chart">
      <ChartContainer
        title="貿易収支"
        showPeriodSelector={false}
        dataSource="SNB"
        sourceUrl="https://data.snb.ch/en/topics/aube"
        handbookId="trade-balance"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={dataKind === 'value' ? '貿易収支' : '前月増減幅'}
          value={currentValue != null ? `CHF ${currentValue >= 0 ? '+' : ''}${currentValue.toFixed(2)}B` : null}
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
                        onClick={() => window.open('/compare?s=ch_balance_of_trade', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {dataKind === 'mom' && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 期間セレクター */}
                  {!(dataKind === 'mom' && displayMode === 'heatmap') && (
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  )}

                  {/* コンテンツ表示 */}
                  {dataKind === 'mom' && displayMode === 'heatmap' && <MonthlyTable data={tableData} />}

                  {dataKind === 'value' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        {
                          dataKey: 'value',
                          color: COLORS.value,
                          name: '貿易収支（B CHF）',
                        },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `CHF ${v >= 0 ? '+' : ''}${v.toFixed(2)}B`}
                    />
                  )}

                  {dataKind === 'mom' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        {
                          dataKey: 'mom_change',
                          color: COLORS.mom,
                          name: '前月増減幅（B CHF）',
                        },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `CHF ${v >= 0 ? '+' : ''}${v.toFixed(2)}B`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ch_balance_of_trade" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
