/**
 * 中国 電気機器在庫チャートコンポーネント
 *
 * 1系列:
 * - yoy: 电气机械和器材制造业存货 累計増減(%)
 *
 * オーバーレイ（右Y軸）:
 * - sox_yoy: SOX指数 前年比(%) ← 7ヶ月先行
 *
 * データソース: NBS（国家統計局）CSVインポート + yfinance SOX
 *
 * FMPマッピング: なし（マーケットインパクトタブなし）
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import { LATEST_VALUE_BOX_STYLE, TEXT_COLORS } from '../../usa/common/chartConstants'
import {
  useSortedData,
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import type { CnElectronicsStockData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnElectronicsStockData | null
}

interface MergedDataPoint {
  date: string
  yoy: number | null
  sox_yoy: number | null
  [key: string]: unknown
}

const COLOR_ELEC_STOCK = '#DC143C'  // Crimson
const COLOR_SOX = '#3b82f6'         // Blue

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

export default function CnElectronicsStockChart({ data }: Props) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries<string>()

  // 電気機器在庫データとSOXデータをdateでマージ
  const chartData = useMemo<MergedDataPoint[]>(() => {
    if (!data) return []

    const soxMap = new Map<string, number | null>()
    for (const item of (data.sox_data ?? [])) {
      soxMap.set(item.date, item.sox_yoy)
    }

    // 電気機器在庫データをベースに、SOXをマージ
    const dateSet = new Set<string>()
    const result: MergedDataPoint[] = []

    // まず電気機器在庫データをすべて追加
    for (const item of (data.data ?? [])) {
      dateSet.add(item.date)
      result.push({
        date: item.date,
        yoy: item.yoy,
        sox_yoy: soxMap.get(item.date) ?? null,
      })
    }

    // SOXにしか存在しない日付を追加
    for (const item of (data.sox_data ?? [])) {
      if (!dateSet.has(item.date)) {
        result.push({
          date: item.date,
          yoy: null,
          sox_yoy: item.sox_yoy,
        })
      }
    }

    return result
  }, [data])

  const sortedData = useSortedData(chartData)
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2012,
  })

  // ローディング
  if (data === null) {
    return (
      <div id="cn-electronics-stock">
        <LoadingChart title="電気機器在庫" />
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div id="cn-electronics-stock">
        <ChartContainer title="電気機器在庫" showPeriodSelector={false} showDataSource={false}>
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  // 最新値
  const latest = data.latest
  const latestSox = data.sox_data?.length > 0 ? data.sox_data[data.sox_data.length - 1] : null

  return (
    <div id="cn-electronics-stock">
      <ChartContainer
        title="電気機器在庫"
        showPeriodSelector={false}
        dataSource="NBS（国家統計局）"
        sourceUrl="https://data.stats.gov.cn/english/easyquery.htm?cn=A01"
      >
        {/* 最新値ボックス */}
        <div style={{ ...LATEST_VALUE_BOX_STYLE, justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {latest?.date && (
              <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>
                {formatDateFull(latest.date)}
              </span>
            )}
            <_LatestBox
              label="電気機器在庫(L)"
              value={latest?.yoy}
              color={COLOR_ELEC_STOCK}
              hidden={hiddenSeries.has('yoy')}
              onClick={() => handleLegendClick('yoy')}
            />
            <_LatestBox
              label="SOX YoY 7M Lead(R)"
              value={latestSox?.sox_yoy}
              color={COLOR_SOX}
              hidden={hiddenSeries.has('sox_yoy')}
              onClick={() => handleLegendClick('sox_yoy')}
            />
          </div>
        </div>

        {/* データ比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 8 }}>
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=cn_electronics_stock', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 期間選択 */}
        <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />

        {/* チャート */}
        <StandardLineChart
          data={filteredData}
          lines={[
            { dataKey: 'yoy', color: COLOR_ELEC_STOCK, name: '電気機器在庫(L)', hide: hiddenSeries.has('yoy') },
            { dataKey: 'sox_yoy', color: COLOR_SOX, name: 'SOX YoY 7M Lead(R)', yAxisId: 'right', hide: hiddenSeries.has('sox_yoy'), strokeDasharray: '6 3' },
          ]}
          xAxisFormatter={formatDateLabel}
          yAxisFormatter={(v: number) => `${v.toFixed(0)}%`}
          rightYAxisFormatter={(v: number) => `${v.toFixed(0)}%`}
          tooltipLabelFormatter={formatDateFull}
          tooltipValueFormatter={(v: number) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : 'N/A'}
          yDomain={['dataMin - 5', 'dataMax + 5']}
          rightYDomain={['dataMin - 10', 'dataMax + 10']}
          showZeroLine={true}
          onLegendClick={handleLegendClick}
        />
      </ChartContainer>
    </div>
  )
}

// =============================================================================
// サブコンポーネント
// =============================================================================

function _LatestBox({
  label,
  value,
  color,
  hidden,
  onClick,
}: {
  label: string
  value: number | null | undefined
  color: string
  hidden: boolean
  onClick: () => void
}) {
  const formatted = value != null
    ? `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
    : '—'

  return (
    <span
      onClick={onClick}
      style={{
        cursor: 'pointer',
        opacity: hidden ? 0.3 : 1,
        marginRight: 8,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
      }}
    >
      <span
        style={{
          display: 'inline-block',
          width: 10,
          height: 10,
          borderRadius: '50%',
          backgroundColor: color,
        }}
      />
      <span style={{ fontSize: 12, color: TEXT_COLORS.secondary }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 700, color }}>
        {formatted}
      </span>
    </span>
  )
}
