/**
 * オーストラリア 住宅ローン金利チャートコンポーネント
 *
 * 既存ローン（Outstanding）と新規ローン（New loans）の
 * 自己居住/投資用の変動金利・固定金利を表示
 *
 * データソース:
 * - RBA Statistical Tables F6 (Housing Lending Rates)
 *
 * 発表スケジュール:
 * - 毎月（月末から5営業日後 11:30 AEDT/AEST）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { AuHousingLendingRatesData } from '../../../../hooks/useDashboardData'

import { LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'
import {
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  ViewModeButtonGroup,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

// カラー設定
const COLORS = {
  outstanding_oo_variable: '#E74C3C',  // 赤 - 既存 自己居住 変動
  outstanding_oo_fixed: '#E67E22',     // オレンジ - 既存 自己居住 固定
  outstanding_inv_variable: '#3498DB', // 青 - 既存 投資 変動
  outstanding_inv_fixed: '#9B59B6',    // 紫 - 既存 投資 固定
  new_oo_variable: '#2ECC71',          // 緑 - 新規 自己居住 変動
  new_oo_fixed: '#1ABC9C',             // ティール - 新規 自己居住 固定
}

type ViewMode = 'outstanding' | 'new'

interface AuHousingLendingRatesChartProps {
  data: AuHousingLendingRatesData | null
}

export default function AuHousingLendingRatesChart({ data }: AuHousingLendingRatesChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(20)
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('outstanding')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  const chartData = useMemo(() => {
    if (!data?.data) return []
    return [...data.data].sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2019,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="住宅ローン金利（オーストラリア）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="住宅ローン金利（オーストラリア）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const latest = data.latest

  // ビューモードに応じた系列
  const outstandingLines = [
    { dataKey: 'outstanding_oo_variable', color: COLORS.outstanding_oo_variable, name: '自己居住 変動', hide: hiddenSeries.has('outstanding_oo_variable') },
    { dataKey: 'outstanding_oo_fixed', color: COLORS.outstanding_oo_fixed, name: '自己居住 固定(≤3yr)', hide: hiddenSeries.has('outstanding_oo_fixed') },
    { dataKey: 'outstanding_inv_variable', color: COLORS.outstanding_inv_variable, name: '投資用 変動', hide: hiddenSeries.has('outstanding_inv_variable') },
    { dataKey: 'outstanding_inv_fixed', color: COLORS.outstanding_inv_fixed, name: '投資用 固定(≤3yr)', hide: hiddenSeries.has('outstanding_inv_fixed') },
  ]

  const newLoansLines = [
    { dataKey: 'new_oo_variable', color: COLORS.new_oo_variable, name: '自己居住 変動', hide: hiddenSeries.has('new_oo_variable') },
    { dataKey: 'new_oo_fixed', color: COLORS.new_oo_fixed, name: '自己居住 固定(≤3yr)', hide: hiddenSeries.has('new_oo_fixed') },
  ]

  const currentLines = viewMode === 'outstanding' ? outstandingLines : newLoansLines

  // 最新値ボックスの表示項目
  const latestItems = viewMode === 'outstanding'
    ? [
        { key: 'outstanding_oo_variable', label: '自己居住 変動', color: COLORS.outstanding_oo_variable },
        { key: 'outstanding_oo_fixed', label: '自己居住 固定', color: COLORS.outstanding_oo_fixed },
        { key: 'outstanding_inv_variable', label: '投資用 変動', color: COLORS.outstanding_inv_variable },
        { key: 'outstanding_inv_fixed', label: '投資用 固定', color: COLORS.outstanding_inv_fixed },
      ]
    : [
        { key: 'new_oo_variable', label: '自己居住 変動', color: COLORS.new_oo_variable },
        { key: 'new_oo_fixed', label: '自己居住 固定', color: COLORS.new_oo_fixed },
      ]

  return (
    <div id="au-housing-lending-rates-chart">
      <ChartContainer
        title="住宅ローン金利"
        showPeriodSelector={false}
        dataSource="RBA"
        sourceUrl="https://www.rba.gov.au/statistics/tables/#interest-rates"
        handbookId="au-housing-lending-rates"
      >
        {/* 最新値表示 */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {latestItems.map(({ key, label, color }) => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span
                style={{
                  width: 12,
                  height: 12,
                  backgroundColor: color,
                  borderRadius: 2,
                }}
              />
              <span style={{ fontSize: 12, color: '#a0a0a0' }}>{label}</span>
              <span style={{ fontSize: 18, fontWeight: 'bold', color }}>
                {latest?.[key as keyof typeof latest] != null
                  ? `${(latest[key as keyof typeof latest] as number).toFixed(2)}%`
                  : '-'}
              </span>
            </div>
          ))}

          {/* 日付・次回発表情報 */}
          <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'flex-end', fontSize: 11, color: '#8c8c8c' }}>
            {latest?.date && <div>{latest.date}</div>}
            {data.next_release && (
              <div>
                次回発表: {data.next_release.date}{data.next_release.label && ` - ${data.next_release.label}`}
              </div>
            )}
          </div>
        </div>

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
                  <ViewModeButtonGroup
                    currentMode={viewMode}
                    onChange={(v) => setViewMode(v as ViewMode)}
                    options={[
                      { mode: 'outstanding', label: '既存ローン' },
                      { mode: 'new', label: '新規ローン' },
                    ]}
                  />

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=au_housing_lending_rates', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={currentLines}
                    yAxisFormatter={(v) => `${v.toFixed(1)}%`}
                    yDomain={['dataMin - 0.3', 'dataMax + 0.3']}
                    tooltipValueFormatter={(v) => `${v.toFixed(2)}%`}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
