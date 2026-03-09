/**
 * ECB M3マネーサプライチャートコンポーネント
 *
 * M3マネーサプライ前年比と指数の推移を表示
 *
 * データソース:
 * - European Central Bank
 * - 前年比: BSI/M.U2.Y.V.M30.X.I.U2.2300.Z01.A
 * - 指数: BSI/M.U2.N.V.M30.X.I.U2.2300.Z01.E (2010年12月=100)
 *
 * 発表スケジュール:
 * - 月次（毎月下旬）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import { usePeriodFiltering, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, SimpleLatestValueBox, StandardLineChart, ViewModeButtonGroup } from '../../usa/common/ChartComponents'
import { CHART_COLORS } from '../../usa/common/chartConstants'

// 型定義
import type { ECBM3Data } from '../../../../hooks/useDashboardData'

interface ECBM3ChartProps {
  data: ECBM3Data | null
}

type DataKind = 'yoy' | 'index'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'yoy', label: '前年比' },
  { mode: 'index', label: '指数' },
]

export default function ECBM3Chart({ data }: ECBM3ChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(10)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('yoy')

  // 前年比データをチャート用に変換
  const yoyChartData = useMemo(() => {
    if (!data?.yoy?.data || data.yoy.data.length === 0) return []

    return data.yoy.data
      .filter((item) => item.value !== null && item.value !== undefined)
      .map((item) => ({
        date: item.date,
        value: item.value,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  // 指数データをチャート用に変換
  const indexChartData = useMemo(() => {
    if (!data?.level?.data || data.level.data.length === 0) return []

    return data.level.data
      .filter((item) => item.value !== null && item.value !== undefined)
      .map((item) => ({
        date: item.date,
        value: item.value,
      }))
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [data])

  // 選択されたビューに応じたデータを使用
  const chartData = dataKind === 'yoy' ? yoyChartData : indexChartData

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2015,
  })

  const hasYoyData = yoyChartData.length > 0
  const hasIndexData = indexChartData.length > 0
  const hasData = hasYoyData || hasIndexData

  // 最新値を取得
  const yoyLatestValue = data?.yoy?.latest
  const indexLatestValue = data?.level?.latest

  // 現在選択されているビューの最新値
  const currentLatestValue = dataKind === 'yoy' ? yoyLatestValue : indexLatestValue

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="M3マネーサプライ" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="M3マネーサプライ" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ecb-m3-chart">
      <ChartContainer
        title="M3マネーサプライ"
        showPeriodSelector={false}
        dataSource="European Central Bank"
        sourceUrl="https://data.ecb.europa.eu/data/datasets/BSI"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={dataKind === 'yoy' ? '前年比' : '指数'}
          value={currentLatestValue?.value}
          valueColor={CHART_COLORS.primary}
          date={currentLatestValue?.date}
          nextRelease={data.next_release ? {
            date: data.next_release.date,
            label: data.next_release.time_jst ? `${data.next_release.time_jst} JST` : undefined
          } : null}
          format={dataKind === 'yoy' ? 'percent' : 'number'}
          decimals={dataKind === 'yoy' ? 2 : 1}
          unit={dataKind === 'index' ? ' (2010.12=100)' : ''}
        />

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ecb_m3_yoy', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>
                  {dataKind === 'yoy' ? (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'value', color: CHART_COLORS.primary, name: 'M3前年比' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                      showZeroLine={true}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
                    />
                  ) : (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'value', color: CHART_COLORS.primary, name: 'M3指数' },
                      ]}
                      yAxisFormatter={(v) => v.toFixed(1)}
                      tooltipValueFormatter={(v) => `${v.toFixed(2)} (2010.12=100)`}
                      yDomain={['dataMin - 5', 'dataMax + 5']}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="monetary_aggregate_m3" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
