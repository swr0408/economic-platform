/**
 * 台湾製造業PMI（S&P Global）チャートコンポーネント
 *
 * データ:
 * - value: S&P Global Manufacturing PMI (Taiwan)
 *
 * データソース:
 * - S&P Global (DB: CSV過去データ + FMP蓄積データ)
 *
 * FMPマッピング: taiwan_pmi_outlook (TW / S&P Global Manufacturing PMI)
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  SimpleLatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { TaiwanManufacturingPmiData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface TaiwanManufacturingPmiChartProps {
  data: TaiwanManufacturingPmiData | null
}

type ActiveTab = 'timeseries' | 'market_impact'

const COLOR_PMI = '#2563eb'

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function TaiwanManufacturingPmiChart({ data }: TaiwanManufacturingPmiChartProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  const sortedData = useSortedData(data?.data ?? [])

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2012,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="台湾製造業PMI" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="台湾製造業PMI" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]

  return (
    <div id="taiwan-manufacturing-pmi">
      <ChartContainer
        title="台湾製造業PMI"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="S&P Global"
        sourceUrl="https://www.pmi.spglobal.com/Public/Release/PressReleases"
        handbookId="taiwan-manufacturing-pmi"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="台湾製造業PMI"
          value={latest?.value}
          valueColor={COLOR_PMI}
          date={latest?.date}
          decimals={1}
          nextRelease={data.next_release ?? undefined}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as ActiveTab)}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=taiwan_manufacturing_pmi', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 期間選択 */}
                  <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

                  {/* 線グラフ */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'value', color: COLOR_PMI, name: '台湾製造業PMI' },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    tooltipValueFormatter={(v) => v != null ? `${v.toFixed(1)}` : 'N/A'}
                    yDomain={['dataMin - 2', 'dataMax + 2']}
                    showZeroLine={false}
                    showFiftyLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="taiwan_pmi_outlook" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
