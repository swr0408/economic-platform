/**
 * EU政府債務残高対GDP比チャートコンポーネント
 *
 * Eurostat gov_10q_ggdebt (General government gross debt, % of GDP)
 * 国別: EA20, DE, FR, IT, ES, EL
 *
 * データソース:
 * - Eurostat
 *
 * 発表スケジュール:
 * - 四半期（T+113日）
 *
 * 単位:
 * - % of GDP
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

import { CHART_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'
import {
  usePeriodFiltering,
  useHiddenSeries,
  useQuarterlyTableData,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  ViewModeButtonGroup,
  NoDataMessage,
  StandardLineChart,
  StandardBarChart,
} from '../../usa/common/ChartComponents'
import { QuarterlyTable } from '../../usa/common/QuarterlyTable'

import type { EUGovernmentDebtToGdpRatioData } from '../../../../hooks/useDashboardData'

interface EuGovernmentDebtToGdpRatioChartProps {
  data: EUGovernmentDebtToGdpRatioData | null
}

type ViewMode = 'value' | 'qoq_chart' | 'qoq_table'

// 国別カラー設定
const COUNTRY_COLORS: Record<string, string> = {
  ea20: CHART_COLORS.primary,     // 青（ユーロ圏）
  de: '#52c41a',                  // 緑（ドイツ）
  fr: '#fa8c16',                  // オレンジ（フランス）
  it: '#f5222d',                  // 赤（イタリア）
  es: '#722ed1',                  // 紫（スペイン）
  el: '#eb2f96',                  // ピンク（ギリシャ）
}

const COUNTRY_LABELS: Record<string, string> = {
  ea20: 'ユーロ圏',
  de: 'ドイツ',
  fr: 'フランス',
  it: 'イタリア',
  es: 'スペイン',
  el: 'ギリシャ',
}

// デフォルト表示国（初期はユーロ圏のみ）
const DEFAULT_VISIBLE = ['ea20']

export default function EuGovernmentDebtToGdpRatioChart({ data }: EuGovernmentDebtToGdpRatioChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [viewMode, setViewMode] = useState<ViewMode>('value')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries(
    // 初期非表示: DEFAULT_VISIBLEに含まれない国
    new Set(Object.keys(COUNTRY_LABELS).filter(k => !DEFAULT_VISIBLE.includes(k)))
  )

  // 国別データをマージして1つのチャートデータに変換
  const chartData = useMemo(() => {
    if (!data?.countries) return []

    // 全日付を収集
    const allDates = new Set<string>()
    Object.values(data.countries).forEach(countryData => {
      countryData.forEach(d => allDates.add(d.date))
    })

    const sortedDates = Array.from(allDates).sort()

    // 各国のデータをMapに
    const countryMaps: Record<string, Map<string, number>> = {}
    for (const [key, countryData] of Object.entries(data.countries)) {
      countryMaps[key] = new Map(countryData.map(d => [d.date, d.value]))
    }

    return sortedDates.map(date => {
      const point: { date: string; [key: string]: unknown } = { date }
      for (const key of Object.keys(COUNTRY_LABELS)) {
        point[key] = countryMaps[key]?.get(date) ?? null
      }
      return point
    })
  }, [data])

  // QoQ変化幅データ（EA20のみ）
  const qoqData = useMemo(() => {
    if (!data?.qoq_change) return []
    return data.qoq_change.map(item => ({
      date: item.date,
      value: item.value,
    }))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  const filteredQoqData = usePeriodFiltering(qoqData, {
    selectedPeriod,
    defaultStartYear: 2010,
  })

  // テーブル用データ（EA20の四半期別マトリックス）
  const qoqTableData = useQuarterlyTableData(
    qoqData,
    (item) => (item as { value: number | null }).value,
    10
  )

  const hasData = chartData.length > 0

  // 最新値を取得（高債務国の最新値を表示）
  const latestValues = useMemo(() => {
    if (!data?.countries) return {}
    const result: Record<string, number | null> = {}
    for (const [key, countryData] of Object.entries(data.countries)) {
      if (countryData.length > 0) {
        result[key] = countryData[countryData.length - 1].value
      }
    }
    return result
  }, [data])

  if (data === null) {
    return <LoadingChart title="政府債務残高対GDP比（ユーロ圏）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="政府債務残高対GDP比（ユーロ圏）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="eu-government-debt-to-gdp-ratio-chart">
      <ChartContainer
        title="政府債務残高対GDP比（ユーロ圏）"
        showPeriodSelector={false}
        dataSource="Eurostat"
        sourceUrl="https://ec.europa.eu/eurostat/databrowser/view/gov_10q_ggdebt"
      >
        {/* 最新値表示（全国） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {Object.keys(COUNTRY_LABELS).map(key => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span
                style={{
                  width: 12,
                  height: 12,
                  backgroundColor: COUNTRY_COLORS[key],
                  borderRadius: 2,
                }}
              />
              <span style={{ fontSize: 12, color: '#a0a0a0' }}>{COUNTRY_LABELS[key]}</span>
              <span style={{ fontSize: 18, fontWeight: 'bold', color: COUNTRY_COLORS[key] }}>
                {latestValues[key] != null ? `${latestValues[key]!.toFixed(1)}%` : '-'}
              </span>
            </div>
          ))}

          {/* 日付・次回発表情報 */}
          <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'flex-end', fontSize: 11, color: '#8c8c8c' }}>
            {data.latest?.date && <div>{data.latest.date}</div>}
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
                    onChange={(mode) => setViewMode(mode)}
                    options={[
                      { mode: 'value', label: '原数値（国別）' },
                      { mode: 'qoq_chart', label: '前期増減幅（EA20）' },
                      { mode: 'qoq_table', label: '前期増減幅（テーブル）' },
                    ]}
                  />

                  {/* テーブル表示 */}
                  {viewMode === 'qoq_table' && (
                    <QuarterlyTable
                      data={qoqTableData}
                      decimals={1}
                      showLegend={false}
                      helperText="※ 直近10年間の前期増減幅データ（単位: %ポイント、EA20）"
                    />
                  )}

                  {/* 期間セレクタ + 比較ボタン */}
                  {viewMode !== 'qoq_table' && (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                        <Tooltip title="比較ページを開く">
                          <Button
                            icon={<AreaChartOutlined />}
                            onClick={() => window.open('/compare?s=eu_government_debt_to_gdp_ratio', '_blank')}
                          >
                            データ比較
                          </Button>
                        </Tooltip>
                      </div>

                      {/* 国別ラインチャート */}
                      {viewMode === 'value' && (
                        <StandardLineChart
                          data={filteredData}
                          lines={Object.keys(COUNTRY_LABELS).map(key => ({
                            dataKey: key,
                            color: COUNTRY_COLORS[key],
                            name: COUNTRY_LABELS[key],
                            hide: hiddenSeries.has(key),
                          }))}
                          yAxisFormatter={(v) => `${v}%`}
                          tooltipValueFormatter={(v) => `${v.toFixed(1)}%`}
                          onLegendClick={handleLegendClick}
                        />
                      )}

                      {/* QoQ変化幅バーチャート（EA20のみ） */}
                      {viewMode === 'qoq_chart' && (
                        <StandardBarChart
                          data={filteredQoqData}
                          bars={[
                            {
                              dataKey: 'value',
                              color: CHART_COLORS.primary,
                              name: '前期増減幅（EA20, %ポイント）',
                            },
                          ]}
                          yAxisFormatter={(v) => `${v}pp`}
                          tooltipValueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}pp`}
                        />
                      )}
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
