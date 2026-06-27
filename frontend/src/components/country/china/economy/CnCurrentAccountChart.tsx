/**
 * 中国 経常収支チャートコンポーネント
 *
 * SAFE (State Administration of Foreign Exchange) Balance of Payments
 * 四半期データ（億USD）
 *
 * ビューモード:
 * - 原数値（棒グラフ）
 * - 前期増減幅（棒グラフ / ヒートマップ）
 *
 * タブ: 時系列 / マーケットインパクト
 *
 * FMPマッピング: cn_current_account
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  usePeriodFiltering,
  useViewModePeriodManagement,
  useQuarterlyTableData,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  SimpleLatestValueBox,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'

import type { CnCurrentAccountData } from '../../../../hooks/useDashboardData'

interface Props {
  data: CnCurrentAccountData | null
}

interface ChartDataPoint {
  date: string
  value: number
  qoq_diff: number | null
  yoy_diff: number | null
  [key: string]: unknown
}

// データ種別
type DataKind = 'value' | 'qoq' | 'yoy'

const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'value', label: '原数値' },
  { mode: 'qoq', label: '前期増減幅' },
  { mode: 'yoy', label: '前年同期差分' },
]

// 表示形式
type DisplayMode = 'chart' | 'heatmap'

const DISPLAY_MODE_OPTIONS: { mode: DisplayMode; label: string }[] = [
  { mode: 'chart', label: 'チャート' },
  { mode: 'heatmap', label: 'ヒートマップ' },
]

const COLORS = {
  value: '#1890ff',
  qoq: '#52c41a',
  yoy: '#fa8c16',
}

export default function CnCurrentAccountChart({ data }: Props) {
  const [dataKind, setDataKind] = useState<DataKind>('value')
  const [displayMode, setDisplayMode] = useState<DisplayMode>('chart')
  const [activeTab, setActiveTab] = useState<string>('timeseries')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    value: 10 as PeriodType,
    qoq: 3 as PeriodType,
    yoy: 10 as PeriodType,
  })

  // チャート用データ変換
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data?.data) return []

    const qoqMap = new Map<string, number>()
    if (data.qoq_diff) {
      data.qoq_diff.forEach(item => {
        qoqMap.set(item.date, item.value)
      })
    }

    const yoyMap = new Map<string, number>()
    if (data.yoy_diff) {
      data.yoy_diff.forEach(item => {
        yoyMap.set(item.date, item.value)
      })
    }

    return data.data
      .map(item => ({
        date: item.date,
        value: item.value,
        qoq_diff: qoqMap.get(item.date) ?? null,
        yoy_diff: yoyMap.get(item.date) ?? null,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2005,
  })

  // テーブル用データ（前期増減幅）
  const qoqTableData = useQuarterlyTableData(
    chartData,
    (item) => item.qoq_diff,
    10
  )

  // テーブル用データ（前年同期差分）
  const yoyTableData = useQuarterlyTableData(
    chartData,
    (item) => item.yoy_diff,
    10
  )

  const hasData = chartData.length > 0

  // 最新値
  const latest = useMemo(() => {
    if (!chartData.length) return null
    return chartData[chartData.length - 1]
  }, [chartData])

  const currentValue = useMemo(() => {
    if (!latest) return null
    if (dataKind === 'value') return latest.value
    if (dataKind === 'qoq') return latest.qoq_diff
    return latest.yoy_diff
  }, [latest, dataKind])

  const currentColor =
    dataKind === 'value' ? COLORS.value : dataKind === 'qoq' ? COLORS.qoq : COLORS.yoy

  if (data === null) {
    return (
      <div id="cn-current-account">
        <LoadingChart title="経常収支" />
      </div>
    )
  }

  if (!hasData) {
    return (
      <div id="cn-current-account">
        <ChartContainer title="経常収支" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const getLabel = () => {
    if (dataKind === 'value') return '経常収支'
    if (dataKind === 'qoq') return '前期増減幅'
    return '前年同期差分'
  }

  const getUnit = () => {
    return '億USD'
  }

  return (
    <div id="cn-current-account">
      <ChartContainer
        title="経常収支"
        showPeriodSelector={false}
        dataSource="SAFE"
        sourceUrl="https://www.safe.gov.cn/en/SAFENews/index.html"
        handbookId="current-account"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={getLabel()}
          value={currentValue != null ? `${currentValue >= 0 ? '+' : ''}${currentValue.toFixed(1)} ${getUnit()}` : null}
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
                  {/* 上段: データ種別 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup
                      currentMode={dataKind}
                      onChange={setDataKind}
                      options={DATA_KIND_OPTIONS}
                    />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_current_account', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 下段: 表示形式（増減幅ビューのとき） */}
                  {(dataKind === 'qoq' || dataKind === 'yoy') && (
                    <div style={{ marginBottom: 8 }}>
                      <ViewModeButtonGroup options={DISPLAY_MODE_OPTIONS} currentMode={displayMode} onChange={setDisplayMode} />
                    </div>
                  )}

                  {/* 期間セレクター */}
                  {!((dataKind === 'qoq' || dataKind === 'yoy') && displayMode === 'heatmap') && (
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                  )}

                  {/* ヒートマップ: 前期増減幅 */}
                  {dataKind === 'qoq' && displayMode === 'heatmap' && (
                    <QuarterlyTable
                      data={qoqTableData}
                      decimals={1}
                      showLegend={false}
                      helperText="※ 直近10年間の前期増減幅データ（単位: 億USD）"
                    />
                  )}

                  {/* ヒートマップ: 前年同期差分 */}
                  {dataKind === 'yoy' && displayMode === 'heatmap' && (
                    <QuarterlyTable
                      data={yoyTableData}
                      decimals={1}
                      showLegend={false}
                      helperText="※ 直近10年間の前年同期差分データ（単位: 億USD）"
                    />
                  )}

                  {/* チャート: 原数値 */}
                  {dataKind === 'value' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'value', color: COLORS.value, name: '経常収支（億USD）' },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)} 億USD`}
                    />
                  )}

                  {/* チャート: 前期増減幅 */}
                  {dataKind === 'qoq' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'qoq_diff', color: COLORS.qoq, name: '前期増減幅（億USD）' },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)} 億USD`}
                    />
                  )}

                  {/* チャート: 前年同期差分 */}
                  {dataKind === 'yoy' && displayMode === 'chart' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'yoy_diff', color: COLORS.yoy, name: '前年同期差分（億USD）' },
                      ]}
                      yAxisFormatter={(v) => `${v}`}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)} 億USD`}
                    />
                  )}

                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="cn_current_account" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
