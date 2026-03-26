/**
 * 韓国輸出（前年比）チャートコンポーネント
 *
 * データ:
 * - value: Exports YoY (%)
 *
 * データソース:
 * - MOTIR (Ministry of Trade, Industry and Resources)
 * - DB: CSV過去データ + FMP蓄積データ
 *
 * FMPマッピング: south_korean_exports (KR / Exports YoY)
 *
 * 注意:
 * - 月初に速報値、月中旬に確報値が発表される
 * - 確報値で上書きされるため、常に最新の値が表示される
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

import type { SouthKoreanExportsData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface SouthKoreanExportsChartProps {
  data: SouthKoreanExportsData | null
}

type ActiveTab = 'timeseries' | 'market_impact'

const COLOR_EXPORTS = '#059669'

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function SouthKoreanExportsChart({ data }: SouthKoreanExportsChartProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)

  const sortedData = useSortedData(data?.data ?? [])

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2016,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="韓国輸出（前年比）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="韓国輸出（前年比）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]

  return (
    <div id="korea-exports">
      <ChartContainer
        title="韓国輸出（前年比）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="MOTIR (Ministry of Trade, Industry and Resources)"
        sourceUrl="https://english.motir.go.kr/eng/article/EATCLdfa319ada"
        handbookId="korea-exports"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="韓国輸出（前年比）"
          value={latest?.value}
          valueColor={COLOR_EXPORTS}
          date={latest?.date}
          decimals={1}
          unit="%"
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
                        onClick={() => window.open('/compare?s=south_korean_exports', '_blank')}
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
                      { dataKey: 'value', color: COLOR_EXPORTS, name: '韓国輸出（前年比）' },
                    ]}
                    yAxisFormatter={(v) => `${v}%`}
                    tooltipValueFormatter={(v) => v != null ? `${v.toFixed(1)}%` : 'N/A'}
                    yDomain={['dataMin - 3', 'dataMax + 3']}
                    showZeroLine={true}
                  />
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="south_korean_exports" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
