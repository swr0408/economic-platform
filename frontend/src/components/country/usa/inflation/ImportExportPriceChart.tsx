/**
 * 輸入物価指数/輸出物価指数チャートコンポーネント
 *
 * FRED IR（輸入物価指数）と IQ（輸出物価指数）の前年比を表示
 * データソース: FRED
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
import type { ImportExportPriceData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useSortedData,
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

interface ImportExportPriceChartProps {
  importExportPriceData: ImportExportPriceData | null
}

// カラー設定
const COLORS = {
  import: '#ef4444',    // 輸入物価指数（赤）
  export: '#3b82f6',    // 輸出物価指数（青）
}

// 項目の日本語名
const LABELS: Record<string, string> = {
  import_yoy: '輸入物価指数',
  export_yoy: '輸出物価指数',
}

// =============================================================================
// カスタムツールチップ
// =============================================================================

function ImportExportPriceTooltip({ active, payload, label }: {
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

export default function ImportExportPriceChart({ importExportPriceData }: ImportExportPriceChartProps) {
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>('default')

  // データを日付昇順にソート
  const sortedData = useSortedData(importExportPriceData?.data)

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2010,
  })

  // 最新値
  const latestImport = useMemo(() => {
    if (!importExportPriceData?.latest) return null
    return importExportPriceData.latest.import_yoy
  }, [importExportPriceData])

  const latestExport = useMemo(() => {
    if (!importExportPriceData?.latest) return null
    return importExportPriceData.latest.export_yoy
  }, [importExportPriceData])

  const latestDate = useMemo(() => {
    if (!importExportPriceData?.latest) return undefined
    return importExportPriceData.latest.date
  }, [importExportPriceData])

  const hasData = sortedData.length > 0

  // ローディング状態
  if (importExportPriceData === null) {
    return <LoadingChart title="輸入物価指数/輸出物価指数" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="輸入物価指数/輸出物価指数" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="import-export-price">
      <ChartContainer
        title="輸入物価指数/輸出物価指数（前年比）"
        showPeriodSelector={false}
        dataSource="FRED"
        sourceUrl="https://fred.stlouisfed.org/series/IR"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={[
            {
              label: LABELS.import_yoy,
              value: latestImport,
              color: COLORS.import,
              format: 'percent',
            },
            {
              label: LABELS.export_yoy,
              value: latestExport,
              color: COLORS.export,
              format: 'percent',
            },
          ]}
          date={latestDate}
          nextRelease={importExportPriceData.next_release}
        />

        {/* 期間セレクタ + 比較ボタン */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
          <Tooltip title="比較ページを開く（輸入物価指数・輸出物価指数）">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=us_import_price_yoy&s=us_export_price_yoy', '_blank')}
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
            <RechartsTooltip content={<ImportExportPriceTooltip />} />
            <Legend />
            <ReferenceLine {...ZERO_LINE_PROPS} />
            <Line
              type="monotone"
              dataKey="import_yoy"
              stroke={COLORS.import}
              strokeWidth={2}
              dot={false}
              name={LABELS.import_yoy}
              isAnimationActive={false}
              connectNulls={true}
            />
            <Line
              type="monotone"
              dataKey="export_yoy"
              stroke={COLORS.export}
              strokeWidth={2}
              dot={false}
              name={LABELS.export_yoy}
              isAnimationActive={false}
              connectNulls={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  )
}
