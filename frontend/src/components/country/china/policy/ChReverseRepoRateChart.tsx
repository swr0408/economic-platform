/**
 * 中国リバースレポ金利（Reverse Repo Rate）チャートコンポーネント
 *
 * データ:
 * - 利率(%) : 7日物リバースレポ金利
 * - 投标量(億元): 応募額
 * - 中标量(億元): 落札額（実際の操作量）
 *
 * データソース:
 * - 中国人民銀行（PBOC）
 * - https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/17081-1.html
 *
 * 更新: 毎営業日 JST 16:00 自動取得
 */
import { useState } from 'react'
import { Button, Tooltip } from 'antd'
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
  StandardBarChart,
  LatestValueBox,
  ViewModeButtonGroup,
} from '../../usa/common/ChartComponents'

import type { ChReverseRepoData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

type ViewMode = 'rate' | 'bid' | 'win'

interface ChReverseRepoRateChartProps {
  data: ChReverseRepoData | null
}

const COLOR_RATE = '#f59e0b'   // 利率（アンバー）
const COLOR_BID  = '#60a5fa'   // 投标量（水色）
const COLOR_WIN  = '#34d399'   // 中标量（緑）

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatDateLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatDateFull = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month, day] = dateStr.split('-')
  return `${year}年${parseInt(month)}月${parseInt(day)}日`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function ChReverseRepoRateChart({ data }: ChReverseRepoRateChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(3)
  const [viewMode, setViewMode] = useState<ViewMode>('rate')

  const sortedData = useSortedData(data?.data ?? [])

  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = sortedData.length > 0

  if (data === null) {
    return <LoadingChart title="リバースレポ金利（7日物）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="リバースレポ金利（7日物）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = sortedData[sortedData.length - 1]

  return (
    <div id="reverse-repo-rate">
      <ChartContainer
        title="リバースレポ金利（7日物）"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="中国人民銀行"
        sourceUrl="https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/17081-1.html"
      >
        {/* 最新値: 利率 + 投标量 + 中标量 を3列表示 */}
        <LatestValueBox
          items={[
            {
              label: '利率',
              value: latest?.value ?? null,
              color: COLOR_RATE,
              format: 'number',
              decimals: 2,
              unit: '%',
            },
            {
              label: '投标量',
              value: latest?.bid_amount ?? null,
              color: COLOR_BID,
              format: 'number',
              decimals: 0,
              unit: '億元',
            },
            {
              label: '中标量',
              value: latest?.win_amount ?? null,
              color: COLOR_WIN,
              format: 'number',
              decimals: 0,
              unit: '億元',
            },
          ]}
          date={latest?.date}
          dateFormatter={formatDateFull}
        />

        {/* ビューモード切替 + データ比較ボタン（同一行） */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <ViewModeButtonGroup
            options={[
              { mode: 'rate' as ViewMode, label: '利率' },
              { mode: 'bid'  as ViewMode, label: '投标量' },
              { mode: 'win'  as ViewMode, label: '中标量' },
            ]}
            currentMode={viewMode}
            onChange={setViewMode}
          />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ch_reverse_repo_rate', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間選択 */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* 利率: 折れ線グラフ */}
        {viewMode === 'rate' && (
          <StandardLineChart
            data={filteredData}
            lines={[
              { dataKey: 'value', color: COLOR_RATE, name: '利率 (%)' },
            ]}
            yAxisFormatter={(v) => `${v.toFixed(2)}%`}
            yDomain={['dataMin - 0.2', 'dataMax + 0.2']}
            xAxisFormatter={formatDateLabel}
            tooltipLabelFormatter={formatDateFull}
            tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
            showZeroLine={false}
            showLegend={false}
          />
        )}

        {/* 投标量: 棒グラフ */}
        {viewMode === 'bid' && (
          <StandardBarChart
            data={filteredData}
            bars={[
              { dataKey: 'bid_amount', color: COLOR_BID, name: '投标量 (億元)' },
            ]}
            yAxisFormatter={(v) => `${Math.round(v).toLocaleString()}`}
            yDomain={[0, 'auto']}
            xAxisFormatter={formatDateLabel}
            tooltipLabelFormatter={formatDateFull}
            tooltipValueFormatter={(v) => `${Math.round(v).toLocaleString()} 億元`}
            showZeroLine={false}
            showLegend={false}
          />
        )}

        {/* 中标量: 棒グラフ */}
        {viewMode === 'win' && (
          <StandardBarChart
            data={filteredData}
            bars={[
              { dataKey: 'win_amount', color: COLOR_WIN, name: '中标量 (億元)' },
            ]}
            yAxisFormatter={(v) => `${Math.round(v).toLocaleString()}`}
            yDomain={[0, 'auto']}
            xAxisFormatter={formatDateLabel}
            tooltipLabelFormatter={formatDateFull}
            tooltipValueFormatter={(v) => `${Math.round(v).toLocaleString()} 億元`}
            showZeroLine={false}
            showLegend={false}
          />
        )}
      </ChartContainer>
    </div>
  )
}
