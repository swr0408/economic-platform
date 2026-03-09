/**
 * Zillow家賃指数 / 家賃CPI チャートコンポーネント
 *
 * Zillow Observed Rent Index (ZORI) と家賃CPIを比較するチャート
 * データソース:
 * - Zillow家賃指数: Zillow CSV直接取得（毎月15日頃更新）
 * - 家賃CPI: FRED CUUR0000SAH1
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
import type { ZillowRentIndexData, RentCPIData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  usePeriodFiltering,
  formatDateLabel,
  type PeriodType,
} from '../common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  ZERO_LINE_PROPS,
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

interface ZillowRentCPIChartProps {
  zillowData: ZillowRentIndexData | null
  rentCPIData: RentCPIData | null
}

interface MergedDataPoint {
  date: string
  zillow: number | null
  rentCPI: number | null
}

// カラー設定
const COLORS = {
  zillow: '#22c55e',     // Zillow家賃指数（緑）
  rentCPI: '#ef4444',    // 家賃CPI（赤）
}

// 項目の日本語名
const LABELS: Record<string, string> = {
  zillow: 'Zillow家賃指数',
  rentCPI: '家賃CPI',
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

function ZillowRentCPITooltip({ active, payload, label }: {
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
        const isRentCPI = item.dataKey === 'rentCPI'
        const displayName = isRentCPI ? LABELS.rentCPI : LABELS.zillow

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
              {item.value.toFixed(2)}%
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

export default function ZillowRentCPIChart({ zillowData, rentCPIData }: ZillowRentCPIChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(10)

  // データをマージ
  const mergedData = useMemo((): MergedDataPoint[] => {
    const map = new Map<string, MergedDataPoint>()

    // Zillowデータを追加
    if (zillowData?.data) {
      zillowData.data.forEach(({ date, yoy }) => {
        map.set(date, {
          date,
          zillow: yoy,
          rentCPI: null
        })
      })
    }

    // 家賃CPIデータを追加
    if (rentCPIData?.data) {
      rentCPIData.data.forEach(({ date, yoy }) => {
        const existing = map.get(date)
        if (existing) {
          existing.rentCPI = yoy
        } else {
          map.set(date, {
            date,
            zillow: null,
            rentCPI: yoy
          })
        }
      })
    }

    return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [zillowData, rentCPIData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(mergedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2016,
  })

  const hasData = mergedData.length > 0

  // ローディング状態
  if (zillowData === null && rentCPIData === null) {
    return <LoadingChart title="Zillow家賃指数 / 家賃CPI" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="Zillow家賃指数 / 家賃CPI" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="zillow-rent-cpi">
      <ChartContainer
        title="Zillow家賃指数 / 家賃CPI（前年比）"
        showPeriodSelector={false}
        dataSource="Zillow / FRED"
        sourceUrl="https://www.zillow.com/research/data/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: LABELS.zillow,
              value: zillowData?.latest?.yoy,
              color: COLORS.zillow,
              format: 'percent',
            },
            {
              label: LABELS.rentCPI,
              value: rentCPIData?.latest?.yoy,
              color: COLORS.rentCPI,
              format: 'percent',
            },
          ]}
          date={zillowData?.latest?.date || rentCPIData?.latest?.date}
        />

        {/* 期間セレクタ + 比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く（Zillow家賃指数・家賃CPI）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=us_zillow_rent_index_yoy&s=us_rent_cpi_standalone_yoy', '_blank')}
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
              domain={[(dataMin: number) => Math.floor(dataMin - 2), (dataMax: number) => Math.ceil(dataMax + 2)]}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v}%`}
            />
            <RechartsTooltip content={<ZillowRentCPITooltip />} />
            <Legend />
            <ReferenceLine {...ZERO_LINE_PROPS} />
            <Line
              type="monotone"
              dataKey="zillow"
              stroke={COLORS.zillow}
              strokeWidth={2}
              dot={false}
              name={LABELS.zillow}
              isAnimationActive={false}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="rentCPI"
              stroke={COLORS.rentCPI}
              strokeWidth={2}
              dot={false}
              name={LABELS.rentCPI}
              isAnimationActive={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
