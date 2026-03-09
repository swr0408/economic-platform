/**
 * 中国 GDP成長率チャートコンポーネント
 *
 * 2系列: 前年比（YoY）/ 前期比（QoQ）
 * 前年比: 折れ線グラフ
 * 前期比: 棒グラフ
 *
 * データソース: NBS（四半期データ）
 *
 * FMPマッピング: cn_gdp_growth_rate
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import {
  useSortedData,
  usePeriodFiltering,
  useViewModePeriodManagement,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  ViewModeButtonGroup,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'

import type { CnGdpGrowthRateData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnGdpGrowthRateData | null
}

interface ChartDataPoint {
  date: string
  yoy: number | null
  qoq: number | null
}

type DataKind = 'yoy' | 'qoq'
const DATA_KIND_OPTIONS: { mode: DataKind; label: string }[] = [
  { mode: 'qoq', label: '前期比' },
  { mode: 'yoy', label: '前年比' },
]

const COLOR_PRIMARY = '#52c41a' // 緑系（経済カテゴリ）

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const quarterMap: Record<string, string> = { '03': 'Q1', '06': 'Q2', '09': 'Q3', '12': 'Q4' }
  return `${year}/${quarterMap[month] ?? month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  const quarterMap: Record<string, string> = { '03': '第1四半期', '06': '第2四半期', '09': '第3四半期', '12': '第4四半期' }
  return `${year}年${quarterMap[month] ?? `${parseInt(month)}月`}`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnGdpGrowthRateChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState('timeseries')
  const [dataKind, setDataKind] = useState<DataKind>('qoq')

  const { currentPeriod, setCurrentPeriod } = useViewModePeriodManagement(dataKind, {
    yoy: 10,
    qoq: 10,
  })

  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data?.data) return []
    return data.data.map(d => ({
      date: d.date,
      yoy: d.yoy,
      qoq: d.qoq,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="GDP成長率" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="GDP成長率" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="gdp">
      <ChartContainer
        title="GDP成長率"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="NBS"
        sourceUrl="https://www.stats.gov.cn/english/PressRelease/index.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label={dataKind === 'yoy' ? 'GDP（YoY）' : 'GDP（QoQ）'}
          value={dataKind === 'yoy' ? (latest?.yoy ?? null) : (latest?.qoq ?? null)}
          date={latest?.date}
          unit="%"
          decimals={1}
          valueColor={COLOR_PRIMARY}
          dateFormatter={formatDateFull}
          nextRelease={data.next_release ?? null}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          size="small"
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* ViewMode + 比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <ViewModeButtonGroup options={DATA_KIND_OPTIONS} currentMode={dataKind} onChange={setDataKind} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_gdp_growth_rate', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* PeriodSelector */}
                  <PeriodSelector
                    onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
                    selectedPeriod={currentPeriod}
                  />

                  {/* 前年比グラフ（折れ線グラフ） */}
                  {dataKind === 'yoy' && (
                    <StandardLineChart
                      data={filteredData}
                      lines={[
                        { dataKey: 'yoy', color: COLOR_PRIMARY, name: 'GDP（前年比）' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                      yDomain={['dataMin - 1', 'dataMax + 1']}
                      xAxisFormatter={formatDateLabel}
                      tooltipLabelFormatter={formatDateFull}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      showZeroLine={true}
                      showLegend={false}
                    />
                  )}

                  {/* 前期比グラフ（棒グラフ） */}
                  {dataKind === 'qoq' && (
                    <StandardBarChart
                      data={filteredData}
                      bars={[
                        { dataKey: 'qoq', color: COLOR_PRIMARY, name: 'GDP（前期比）' },
                      ]}
                      yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                      yDomain={['dataMin - 0.5', 'dataMax + 0.5']}
                      xAxisFormatter={formatDateLabel}
                      tooltipLabelFormatter={formatDateFull}
                      tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                    />
                  )}
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="cn_gdp_growth_rate" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
