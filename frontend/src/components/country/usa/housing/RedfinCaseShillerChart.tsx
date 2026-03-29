/**
 * Redfin住宅価格中央値 & ケースシラー住宅価格指数チャートコンポーネント
 *
 * 2つのデータソースを1つの複合チャートで表示:
 * - Redfin 全米住宅価格中央値（前年比）
 * - S&P/ケースシラー住宅価格指数（前年比）
 *
 * データソース:
 * - Redfin Data Center
 * - FRED (SPCS20RSA)
 */
import { useState, useMemo } from 'react'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type {
  RedfinMedianPriceData,
  CaseShillerData,
} from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  formatDateLabel,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  type TooltipPayloadItem,
} from '../common/ChartComponents'
import {
  TOOLTIP_STYLE,
  CHART_MARGIN,
  AXIS_STYLE,
  CARTESIAN_GRID_PROPS,
  DARK_THEME,
} from '../common/chartConstants'

// =============================================================================
// 型定義
// =============================================================================

interface RedfinCaseShillerChartProps {
  redfinMedianPriceData: RedfinMedianPriceData | null
  caseShillerData: CaseShillerData | null
}

interface MergedDataPoint {
  date: string
  redfin: number | null
  caseShiller: number | null
}

// カラー設定
const COLORS = {
  redfin: '#e74c3c',      // 赤（Redfin）
  caseShiller: '#3498db', // 青（ケースシラー）
}

// 項目の日本語名
const LABELS: Record<string, string> = {
  redfin: 'Redfin 住宅価格中央値（前年比）',
  caseShiller: 'ケースシラー住宅価格指数（前年比）',
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

function RedfinCaseShillerTooltip({ active, payload, label }: {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
        {formatDateLabel(label || '')}
      </div>
      {payload.map((item, index) => {
        const displayName = LABELS[item.dataKey] || item.name

        return (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
              fontSize: 13,
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', marginRight: 16, color: '#f1f5f9' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  backgroundColor: item.color,
                  marginRight: 6,
                }}
              />
              {displayName}
            </span>
            <span style={{ fontWeight: 500, color: item.color }}>
              {item.value != null ? `${item.value.toFixed(2)}%` : '-'}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function RedfinCaseShillerChart({
  redfinMedianPriceData,
  caseShillerData,
}: RedfinCaseShillerChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(10)

  // データをマージ（2つの系列を1つの配列に結合）
  const mergedData = useMemo((): MergedDataPoint[] => {
    const redfinData = redfinMedianPriceData?.data || []
    const caseShillerDataItems = caseShillerData?.data || []

    // 全日付を収集
    const dateSet = new Set<string>()
    redfinData.forEach(d => dateSet.add(d.date))
    caseShillerDataItems.forEach(d => dateSet.add(d.date))

    // 日付ごとにデータをマージ
    const redfinMap = new Map(redfinData.map(d => [d.date, d.value]))
    const caseShillerMap = new Map(caseShillerDataItems.map(d => [d.date, d.yoy]))

    const result: MergedDataPoint[] = []
    dateSet.forEach(date => {
      result.push({
        date,
        redfin: redfinMap.get(date) ?? null,
        caseShiller: caseShillerMap.get(date) ?? null,
      })
    })

    // 日付昇順でソート
    return result.sort((a, b) => a.date.localeCompare(b.date))
  }, [redfinMedianPriceData, caseShillerData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(mergedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2013, // 両方のデータが揃い始める年
  })

  // 最新値
  const latestRedfin = useMemo(() => {
    return redfinMedianPriceData?.latest?.value ?? null
  }, [redfinMedianPriceData])

  const latestCaseShiller = useMemo(() => {
    return caseShillerData?.latest?.yoy ?? null
  }, [caseShillerData])

  const latestRedfinDate = useMemo(() => {
    return redfinMedianPriceData?.latest?.date
  }, [redfinMedianPriceData])

  const latestCaseShillerDate = useMemo(() => {
    return caseShillerData?.latest?.date
  }, [caseShillerData])

  const hasData = mergedData.length > 0

  // ローディング状態（両方nullの場合）
  if (redfinMedianPriceData === null && caseShillerData === null) {
    return <LoadingChart title="住宅価格指数 (前年比)" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="住宅価格指数 (前年比)" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="redfin-case-shiller">
      <ChartContainer
        title="Redfin住宅価格中央値 / ケースシラー住宅価格指数"
        showPeriodSelector={false}
        dataSource="Redfin, FRED"
        sourceUrl="https://www.redfin.com/news/data-center/"
        handbookId="redfin-case-shiller"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: `Redfin住宅価格中央値（前年比）${latestRedfinDate ? ` [${formatDateLabel(latestRedfinDate)}]` : ''}`,
              value: latestRedfin,
              color: COLORS.redfin,
              format: 'percent',
            },
            {
              label: `ケースシラー指数（前年比）${latestCaseShillerDate ? ` [${formatDateLabel(latestCaseShillerDate)}]` : ''}`,
              value: latestCaseShiller,
              color: COLORS.caseShiller,
              format: 'percent',
            },
          ]}
          nextRelease={caseShillerData?.next_release}
        />

        {/* 期間セレクタ + 比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く（住宅価格指数）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=us_redfin_median_price_yoy&s=us_case_shiller_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 折れ線グラフ */}
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={AXIS_STYLE.tick}
              interval={AXIS_STYLE.interval}
            />
            <YAxis
              domain={['dataMin - 2', 'dataMax + 2']}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v}%`}
            />
            <RechartsTooltip content={<RedfinCaseShillerTooltip />} />
            <Legend />
            {/* ゼロライン */}
            <ReferenceLine
              y={0}
              stroke="#64748b"
              strokeDasharray="3 3"
            />
            <Line
              type="monotone"
              dataKey="redfin"
              stroke={COLORS.redfin}
              strokeWidth={2}
              dot={false}
              name={LABELS.redfin}
              isAnimationActive={false}
              connectNulls={true}
            />
            <Line
              type="monotone"
              dataKey="caseShiller"
              stroke={COLORS.caseShiller}
              strokeWidth={2}
              dot={false}
              name={LABELS.caseShiller}
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
