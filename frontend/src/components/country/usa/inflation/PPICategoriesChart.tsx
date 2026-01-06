/**
 * PPI項目別チャートコンポーネント
 *
 * 航空、ポートフォリオ管理、医療関連など7項目の前年比を表示
 * PCEデフレーター算出に使用される項目
 * 項目が多いためテーブル/グラフ切替で表示
 * 航空・ポートフォリオ管理は変動が大きいため右Y軸
 */
import { useState, useMemo } from 'react'
import { Tabs, Table, Button, Tooltip } from 'antd'
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
import type { PPICategoriesData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import {
  useHiddenSeries,
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

interface PPICategoriesChartProps {
  categoriesData: PPICategoriesData | null
}

// 表示モード（前月比テーブルとグラフのみ）
type ViewMode = 'table' | 'chart'

// マージ済みデータの型
interface MergedDataItem {
  date: string
  [key: string]: string | number | null
}

// カラー設定（7項目）
const COLORS: Record<string, string> = {
  airline_passenger: '#ef4444',     // 航空会社乗客サービス（赤）
  portfolio_management: '#f97316',  // ポートフォリオ管理（オレンジ）
  medical_care: '#3b82f6',          // 医療ケア（青）
  home_health_hospice: '#a855f7',   // 在宅医療・ホスピスケア（紫）
  hospital_outpatient: '#10b981',   // 病院外来医療（緑）
  hospital_inpatient: '#eab308',    // 病院入院治療（黄）
  nursing_home: '#ec4899',          // 特別養護老人ホームケア（ピンク）
}

// 項目の日本語名（短縮版）
const CATEGORY_LABELS: Record<string, string> = {
  airline_passenger: '航空会社乗客サービス',
  portfolio_management: 'ポートフォリオ管理',
  medical_care: '医療ケア',
  home_health_hospice: '在宅医療・ホスピスケア',
  hospital_outpatient: '病院外来医療',
  hospital_inpatient: '病院入院治療',
  nursing_home: '特別養護老人ホームケア',
}

// 項目の日本語名（フル版）
const CATEGORY_LABELS_FULL: Record<string, string> = {
  airline_passenger: '航空会社乗客サービス',
  portfolio_management: 'ポートフォリオ管理',
  medical_care: '医療ケア',
  home_health_hospice: '在宅医療・ホスピスケア',
  hospital_outpatient: '病院外来医療',
  hospital_inpatient: '病院入院治療',
  nursing_home: '特別養護老人ホームケア',
}

// カテゴリの表示順序
const CATEGORY_ORDER = [
  'airline_passenger',
  'portfolio_management',
  'medical_care',
  'home_health_hospice',
  'hospital_outpatient',
  'hospital_inpatient',
  'nursing_home',
]

// 右Y軸に表示するカテゴリ（変動が大きい項目）
const RIGHT_AXIS_CATEGORIES = ['airline_passenger', 'portfolio_management']

// 左Y軸に表示するカテゴリ
const LEFT_AXIS_CATEGORIES = CATEGORY_ORDER.filter(k => !RIGHT_AXIS_CATEGORIES.includes(k))

// =============================================================================
// カスタムツールチップ
// =============================================================================

function CategoryTooltip({ active, payload, label }: {
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
        const isRightAxis = RIGHT_AXIS_CATEGORIES.includes(item.dataKey)
        const displayName = isRightAxis
          ? `${CATEGORY_LABELS[item.dataKey]}（右軸）`
          : CATEGORY_LABELS[item.dataKey] || item.name
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

export default function PPICategoriesChart({ categoriesData }: PPICategoriesChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('table')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodType>(5)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [displayCount, setDisplayCount] = useState<number>(5) // 初期表示5件
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // カテゴリデータをチャート用にマージ（YoY用）
  const mergedData = useMemo(() => {
    if (!categoriesData?.categories) return []

    // 全日付を収集
    const dateSet = new Set<string>()
    for (const category of categoriesData.categories) {
      for (const item of category.data) {
        dateSet.add(item.date)
      }
    }

    // カテゴリキーごとにデータをマップ
    const categoryDataMaps: Record<string, Map<string, number | null>> = {}
    for (const category of categoriesData.categories) {
      const map = new Map<string, number | null>()
      for (const item of category.data) {
        map.set(item.date, item.yoy)
      }
      categoryDataMaps[category.key] = map
    }

    // 日付ごとにデータをマージ
    const result: MergedDataItem[] = []
    for (const date of Array.from(dateSet).sort()) {
      const row: MergedDataItem = { date }
      for (const key of CATEGORY_ORDER) {
        row[key] = categoryDataMaps[key]?.get(date) ?? null
      }
      result.push(row)
    }

    return result
  }, [categoriesData])

  // 期間フィルタリング（手動実装 - 1Y〜5Y対応）
  const filteredData = useMemo(() => {
    if (!mergedData.length) return []

    if (currentPeriod === 'default' || currentPeriod === 'all') {
      return mergedData
    }

    const years = typeof currentPeriod === 'number' ? currentPeriod : 5
    const now = new Date()
    const cutoffDate = new Date(now.getFullYear() - years, now.getMonth(), 1)
    const cutoffStr = cutoffDate.toISOString().slice(0, 10)

    return mergedData.filter(item => item.date >= cutoffStr)
  }, [mergedData, currentPeriod])

  // 前月比テーブル用データ（年月行×カテゴリ列）- 最新順
  const tableData = useMemo(() => {
    if (!categoriesData?.categories) return []

    // 最新10年分のデータを使用
    const years: number[] = []
    const currentYear = new Date().getFullYear()
    for (let y = currentYear; y >= currentYear - 9; y--) {
      years.push(y)
    }

    const months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

    // カテゴリごとのMoMデータマップを作成
    const categoryDataMaps: Record<string, Map<string, number | null>> = {}
    for (const category of categoriesData.categories) {
      const map = new Map<string, number | null>()
      for (const item of category.data) {
        map.set(item.date, item.mom ?? null)
      }
      categoryDataMaps[category.key] = map
    }

    // 年月行を生成
    const result: Record<string, unknown>[] = []
    for (const year of years) {
      for (const month of months) {
        const dateKey = `${year}-${String(month).padStart(2, '0')}-01`
        const row: Record<string, unknown> = {
          key: dateKey,
          year,
          month,
          date: dateKey,
        }

        // 各カテゴリの値を追加
        for (const key of CATEGORY_ORDER) {
          row[key] = categoryDataMaps[key]?.get(dateKey) ?? null
        }

        // 少なくとも1つの値がある行のみ追加
        const hasValue = CATEGORY_ORDER.some(key => row[key] !== null)
        if (hasValue) {
          result.push(row)
        }
      }
    }

    return result.sort((a, b) => (b.date as string).localeCompare(a.date as string))
  }, [categoriesData])

  // 表示するテーブルデータ
  const displayedTableData = tableData.slice(0, displayCount)
  const hasMoreData = tableData.length > displayCount

  const hasData = categoriesData?.categories && categoriesData.categories.length > 0

  // ローディング状態
  if (categoriesData === null) {
    return <LoadingChart title="PPI 項目別" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="PPI 項目別" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値を各カテゴリから取得（ビューモードに応じてYoY/MoMを切替）
  const latestItems = categoriesData.categories.map(cat => ({
    label: CATEGORY_LABELS[cat.key] || cat.name,
    value: viewMode === 'table' ? cat.latest?.mom : cat.latest?.yoy,
    color: COLORS[cat.key] || '#94a3b8',
    format: 'percent' as const,
  }))

  // テーブルカラム定義（幅を狭く）
  const tableColumns = [
    {
      title: '年月',
      dataIndex: 'date',
      key: 'date',
      fixed: 'left' as const,
      width: 80,
      render: (date: string) => {
        const d = new Date(date)
        return `${d.getFullYear()}/${d.getMonth() + 1}`
      },
    },
    ...CATEGORY_ORDER.map(key => ({
      title: CATEGORY_LABELS[key],
      dataIndex: key,
      key,
      align: 'right' as const,
      render: (value: number | null) => {
        if (value === null) return '-'
        const color = value >= 0 ? '#ef4444' : '#3b82f6'
        return <span style={{ color }}>{value.toFixed(1)}%</span>
      },
    })),
  ]

  // 追加表示ハンドラ
  const handleLoadMore = () => {
    setDisplayCount(prev => prev + 10)
  }

  // リセットハンドラ
  const handleReset = () => {
    setDisplayCount(5)
  }

  return (
    <div id="ppi-categories">
      <ChartContainer
        title="PPI PCE関連項目"
        showPeriodSelector={false}
        dataSource="BLS"
        sourceUrl="https://www.bls.gov/news.release/ppi.nr0.htm"
      >
        {/* 最新値表示 */}
        <LatestValueBox
          items={latestItems}
          date={categoriesData.categories[0]?.latest?.date}
          nextRelease={categoriesData.next_release}
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
                  {/* 表示モード切替 */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <Button
                        type={viewMode === 'table' ? 'primary' : 'default'}
                        onClick={() => { setViewMode('table'); setDisplayCount(5) }}
                        size="small"
                      >
                        前月比テーブル
                      </Button>
                      <Button
                        type={viewMode === 'chart' ? 'primary' : 'default'}
                        onClick={() => setViewMode('chart')}
                        size="small"
                      >
                        前年比グラフ
                      </Button>
                    </div>
                    <Tooltip title="比較ページを開く（PPI項目別）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => {
                          const params = CATEGORY_ORDER.map(key => `s=us_ppi_${key}_yoy`).join('&')
                          window.open(`/compare?${params}`, '_blank')
                        }}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* テーブル表示（前月比） */}
                  {viewMode === 'table' && (
                    <>
                      <Table
                        dataSource={displayedTableData}
                        columns={tableColumns}
                        pagination={false}
                        scroll={{ x: 700 }}
                        size="small"
                        style={{ marginTop: 8 }}
                      />
                      <div style={{ textAlign: 'center', marginTop: 12, display: 'flex', justifyContent: 'center', gap: 8 }}>
                        {hasMoreData && (
                          <Button onClick={handleLoadMore}>
                            さらに10件表示
                          </Button>
                        )}
                        {displayCount > 5 && (
                          <Button onClick={handleReset}>
                            リセット
                          </Button>
                        )}
                      </div>
                    </>
                  )}

                  {/* グラフ表示 */}
                  {viewMode === 'chart' && (
                    <>
                      <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                      <ResponsiveContainer width="100%" height={450}>
                        <LineChart data={filteredData} margin={CHART_MARGIN}>
                          <CartesianGrid {...CARTESIAN_GRID_PROPS} />
                          <XAxis
                            dataKey="date"
                            tickFormatter={formatDateLabel}
                            tick={AXIS_STYLE.tick}
                            interval={AXIS_STYLE.interval}
                          />
                          {/* 左Y軸（医療関連） */}
                          <YAxis
                            yAxisId="left"
                            domain={[(dataMin: number) => Math.floor(dataMin - 1), (dataMax: number) => Math.ceil(dataMax + 1)]}
                            tick={AXIS_STYLE.tick}
                            tickFormatter={(v) => `${v}%`}
                          />
                          {/* 右Y軸（航空・ポートフォリオ） */}
                          <YAxis
                            yAxisId="right"
                            orientation="right"
                            domain={[(dataMin: number) => Math.floor(dataMin - 1), (dataMax: number) => Math.ceil(dataMax + 1)]}
                            tick={{ ...AXIS_STYLE.tick, fill: COLORS.airline_passenger }}
                            tickFormatter={(v) => `${v}%`}
                          />
                          <RechartsTooltip content={<CategoryTooltip />} />
                          <Legend
                            onClick={(e) => handleLegendClick(e.dataKey as string)}
                            wrapperStyle={{ cursor: 'pointer' }}
                          />
                          <ReferenceLine yAxisId="left" {...ZERO_LINE_PROPS} />
                          {/* 左Y軸の線（医療関連） */}
                          {LEFT_AXIS_CATEGORIES.map(key => (
                            <Line
                              key={key}
                              yAxisId="left"
                              type="monotone"
                              dataKey={key}
                              stroke={COLORS[key]}
                              strokeWidth={2}
                              dot={false}
                              name={CATEGORY_LABELS_FULL[key]}
                              hide={hiddenSeries.has(key)}
                              isAnimationActive={false}
                              connectNulls={true}
                            />
                          ))}
                          {/* 右Y軸の線（航空・ポートフォリオ） */}
                          {RIGHT_AXIS_CATEGORIES.map(key => (
                            <Line
                              key={key}
                              yAxisId="right"
                              type="monotone"
                              dataKey={key}
                              stroke={COLORS[key]}
                              strokeWidth={2}
                              dot={false}
                              name={`${CATEGORY_LABELS_FULL[key]}（右軸）`}
                              hide={hiddenSeries.has(key)}
                              isAnimationActive={false}
                              connectNulls={true}
                            />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    </>
                  )}
                </>
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
