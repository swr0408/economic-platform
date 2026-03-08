/**
 * 中国ローンプライムレート（Loan Prime Rate）チャートコンポーネント
 *
 * データ:
 * - 1Y LPR: 1年物ローンプライムレート（%）
 * - 5Y LPR: 5年物ローンプライムレート（%）
 *
 * データソース:
 * - 中国人民銀行（PBOC）
 * - https://www.pbc.gov.cn/
 *
 * FMPマッピング:
 * - Loan Prime Rate 1Y (econalpha_id: cn_lpr_1y)
 * - Loan Prime Rate 5Y (econalpha_id: cn_lpr_5y)
 */
import { useState } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import {
  useSortedData,
  usePeriodFiltering,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
  LatestValueBox,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CnLprData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface CnLprChartProps {
  lpr1y: CnLprData | null
  lpr5y: CnLprData | null
}

// カラー設定
const COLOR_1Y = '#ef4444'    // 1Y LPR（赤）
const COLOR_5Y = '#3b82f6'    // 5Y LPR（青）

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateLabelJP = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month)}月`
}

// =============================================================================
// データマージ
// =============================================================================

interface MergedDataPoint {
  date: string
  lpr_1y: number | null
  lpr_5y: number | null
}

function mergeLprData(data1y: { date: string; value: number | null }[], data5y: { date: string; value: number | null }[]): MergedDataPoint[] {
  const map: Record<string, MergedDataPoint> = {}

  for (const item of data1y) {
    if (!map[item.date]) map[item.date] = { date: item.date, lpr_1y: null, lpr_5y: null }
    map[item.date].lpr_1y = item.value
  }
  for (const item of data5y) {
    if (!map[item.date]) map[item.date] = { date: item.date, lpr_1y: null, lpr_5y: null }
    map[item.date].lpr_5y = item.value
  }

  return Object.values(map).sort((a, b) => a.date.localeCompare(b.date))
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function CnLprChart({ lpr1y, lpr5y }: CnLprChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>('default')

  // 1Y データのソート
  const sorted1y = useSortedData(lpr1y?.data ?? [])
  // 5Y データのソート
  const sorted5y = useSortedData(lpr5y?.data ?? [])

  // マージデータ作成
  const mergedData = mergeLprData(sorted1y, sorted5y)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(mergedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2019,
  })

  const hasData = mergedData.length > 0

  // ローディング状態
  if (lpr1y === null && lpr5y === null) {
    return <LoadingChart title="ローンプライムレート (LPR)" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="ローンプライムレート (LPR)" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest1y = sorted1y[sorted1y.length - 1]
  const latest5y = sorted5y[sorted5y.length - 1]
  const nextRelease = lpr1y?.next_release ?? lpr5y?.next_release ?? null

  return (
    <div id="lpr">
      <ChartContainer
        title="ローンプライムレート (LPR)"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中国人民銀行"
        sourceUrl="https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125440/index.html"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: '1Y LPR',
              value: latest1y?.value ?? null,
              color: COLOR_1Y,
              format: 'number',
              decimals: 2,
              unit: '%',
            },
            {
              label: '5Y LPR',
              value: latest5y?.value ?? null,
              color: COLOR_5Y,
              format: 'number',
              decimals: 2,
              unit: '%',
            },
          ]}
          date={latest1y?.date ?? latest5y?.date}
          dateFormatter={formatDateLabelJP}
          nextRelease={nextRelease ? { date: nextRelease.date } : undefined}
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
                  {/* 期間選択 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_lpr_1y&s=cn_lpr_5y', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* LPR 折れ線グラフ（1Y + 5Y 同時表示） */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'lpr_1y', color: COLOR_1Y, name: '1Y LPR' },
                      { dataKey: 'lpr_5y', color: COLOR_5Y, name: '5Y LPR' },
                    ]}
                    yAxisFormatter={(v) => `${v.toFixed(2)}%`}
                    yDomain={['dataMin - 0.2', 'dataMax + 0.2']}
                    xAxisFormatter={formatDateLabel}
                    tooltipLabelFormatter={formatDateLabelJP}
                    tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                  />
                </>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="cn_lpr_1y" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
