/**
 * 住宅関連指標チャートコンポーネント
 *
 * Zillow家賃指数、ケースシラー住宅価格指数（18か月先行）と家賃CPIを比較
 * 家賃CPIは右Y軸に表示
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
import type { HousingIndicatorsData } from '../../../../hooks/useDashboardData'

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

interface HousingIndicatorsChartProps {
  housingData: HousingIndicatorsData | null
}

interface MergedDataPoint {
  date: string
  zillow: number | null
  caseShiller: number | null
  rentCPI: number | null
}

// カラー設定
const COLORS = {
  zillow: '#22c55e',      // Zillow家賃指数（緑）
  caseShiller: '#3b82f6', // ケースシラー（青）
  rentCPI: '#ef4444',     // 家賃CPI（赤）
}

// 項目の日本語名
const LABELS: Record<string, string> = {
  zillow: 'Zillow家賃指数',
  caseShiller: 'ケースシラー住宅価格指数',
  rentCPI: '家賃CPI',
}

// =============================================================================
// 18か月先行シフト関数
// =============================================================================

function shiftDataForward(data: { date: string; yoy: number }[], months: number): { date: string; yoy: number }[] {
  return data.map(point => {
    const date = new Date(point.date)
    date.setMonth(date.getMonth() + months)
    const shiftedDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`
    return {
      date: shiftedDate,
      yoy: point.yoy
    }
  })
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

function HousingTooltip({ active, payload, label }: {
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
        const isZillow = item.dataKey === 'zillow'
        const isCaseShiller = item.dataKey === 'caseShiller'
        let displayName = item.name
        if (isZillow) displayName = `${LABELS.zillow}:18か月先行(L)`
        else if (isCaseShiller) displayName = `${LABELS.caseShiller}:18か月先行(L)`
        else if (isRentCPI) displayName = `${LABELS.rentCPI}(R)`

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

export default function HousingIndicatorsChart({ housingData }: HousingIndicatorsChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>('default')

  // データをマージ（ZillowとケースシラーをR18か月先行させて家賃CPIと結合）
  const mergedData = useMemo((): MergedDataPoint[] => {
    if (!housingData?.data) return []

    const { zillow, case_shiller, rent_cpi } = housingData.data
    if (!zillow || !case_shiller || !rent_cpi) return []

    // ZillowとCase-Shillerを18か月先行させる
    const zillowShifted = shiftDataForward(zillow, 18)
    const caseShillerShifted = shiftDataForward(case_shiller, 18)

    const map = new Map<string, MergedDataPoint>()

    // 家賃CPIをベースにする
    rent_cpi.forEach(({ date, yoy }) => {
      map.set(date, {
        date,
        zillow: null,
        caseShiller: null,
        rentCPI: yoy
      })
    })

    // シフトされたZillowデータを追加
    zillowShifted.forEach(({ date, yoy }) => {
      const existing = map.get(date)
      if (existing) {
        existing.zillow = yoy
      } else {
        map.set(date, {
          date,
          zillow: yoy,
          caseShiller: null,
          rentCPI: null
        })
      }
    })

    // シフトされたCase-Shillerデータを追加
    caseShillerShifted.forEach(({ date, yoy }) => {
      const existing = map.get(date)
      if (existing) {
        existing.caseShiller = yoy
      } else {
        map.set(date, {
          date,
          zillow: null,
          caseShiller: yoy,
          rentCPI: null
        })
      }
    })

    return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [housingData])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(mergedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = mergedData.length > 0

  // ローディング状態
  if (housingData === null) {
    return <LoadingChart title="住宅関連指標" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="住宅関連指標" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = housingData.latest

  return (
    <div id="housing-indicators">
      <ChartContainer
        title="Zillow家賃指数 / ケースシラー住宅価格指数 / 家賃CPI"
        showPeriodSelector={false}
        dataSource="FRED / Zillow"
        sourceUrl="https://www.zillow.com/research/data/"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: LABELS.zillow,
              value: latest?.zillow?.yoy,
              color: COLORS.zillow,
              format: 'percent',
            },
            {
              label: LABELS.caseShiller,
              value: latest?.case_shiller?.yoy,
              color: COLORS.caseShiller,
              format: 'percent',
            },
            {
              label: LABELS.rentCPI,
              value: latest?.rent_cpi?.yoy,
              color: COLORS.rentCPI,
              format: 'percent',
            },
          ]}
          date={latest?.rent_cpi?.date}
        />

        {/* 期間セレクタ + 比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く（Zillow家賃指数・ケースシラー・家賃CPI）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=us_zillow_rent_yoy&s=us_case_shiller_yoy&s=us_rent_cpi_yoy', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {/* 折れ線グラフ（家賃CPIは右Y軸） */}
        <ResponsiveContainer width="100%" height={450}>
          <LineChart data={filteredData} margin={CHART_MARGIN}>
            <CartesianGrid {...CARTESIAN_GRID_PROPS} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={AXIS_STYLE.tick}
              interval={AXIS_STYLE.interval}
            />
            {/* 左Y軸（Zillow、ケースシラー） */}
            <YAxis
              yAxisId="left"
              domain={[(dataMin: number) => Math.floor(dataMin - 2), (dataMax: number) => Math.ceil(dataMax + 2)]}
              tick={AXIS_STYLE.tick}
              tickFormatter={(v) => `${v}%`}
            />
            {/* 右Y軸（家賃CPI） */}
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[(dataMin: number) => Math.floor(dataMin - 1), (dataMax: number) => Math.ceil(dataMax + 1)]}
              tick={{ ...AXIS_STYLE.tick, fill: COLORS.rentCPI }}
              tickFormatter={(v) => `${v}%`}
            />
            <RechartsTooltip content={<HousingTooltip />} />
            <Legend />
            <ReferenceLine yAxisId="left" {...ZERO_LINE_PROPS} />
            {/* 左Y軸の線 */}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="zillow"
              stroke={COLORS.zillow}
              strokeWidth={2}
              dot={false}
              name={`${LABELS.zillow}:18か月先行(L)`}
              isAnimationActive={false}
              connectNulls={false}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="caseShiller"
              stroke={COLORS.caseShiller}
              strokeWidth={2}
              dot={false}
              name={`${LABELS.caseShiller}:18か月先行(L)`}
              isAnimationActive={false}
              connectNulls={false}
            />
            {/* 右Y軸の線（家賃CPI） */}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="rentCPI"
              stroke={COLORS.rentCPI}
              strokeWidth={2}
              dot={false}
              name={`${LABELS.rentCPI}(R)`}
              isAnimationActive={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
