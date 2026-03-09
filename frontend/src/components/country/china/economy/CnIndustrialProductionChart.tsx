/**
 * 中国 鉱工業生産（Industrial Production）チャートコンポーネント
 *
 * 1系列: 鉱工業生産 前年比 (YoY%)
 * 折れ線グラフ
 *
 * データソース: NBS
 *
 * FMPマッピング: cn_industrial_production → "Industrial Production YoY"
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
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { CnIndustrialProductionData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnIndustrialProductionData | null
}

interface ChartDataPoint {
  date: string
  yoy: number | null
}

const COLOR_PRIMARY = '#389e0d' // 緑系（経済カテゴリ）

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnIndustrialProductionChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data?.data) return []
    return data.data.map(d => ({
      date: d.date,
      yoy: d.yoy,
    }))
  }, [data])

  const sortedData = useSortedData(chartData)

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="鉱工業生産" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="鉱工業生産" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  return (
    <div id="industrial-production">
      <ChartContainer
        title="鉱工業生産"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="NBS"
        sourceUrl="https://www.stats.gov.cn/english/PressRelease/index.html"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="鉱工業生産（YoY）"
          value={latest?.yoy ?? null}
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
                  {/* 比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_industrial_production', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <PeriodSelector
                    onPeriodChange={(p: PeriodValue) => setCurrentPeriod(p)}
                    selectedPeriod={currentPeriod}
                  />
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'yoy', color: COLOR_PRIMARY, name: '鉱工業生産（前年比）' },
                    ]}
                    yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                    yDomain={['dataMin - 2', 'dataMax + 2']}
                    xAxisFormatter={formatDateLabel}
                    tooltipLabelFormatter={formatDateFull}
                    tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                    showZeroLine={true}
                    showLegend={false}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="cn_industrial_production" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
