/**
 * 中国 Caixin PMI チャートコンポーネント
 *
 * 2系列: 財新製造業PMI + 財新サービス業PMI
 * 折れ線グラフ（50ラインをゼロ線として表示）
 *
 * データソース: S&P Global / Caixin
 *
 * FMPマッピング:
 * - cn_caixin_manufacturing_pmi
 * - cn_caixin_service_pmi
 *
 * 注意: 製造業とサービス業は発表日が異なるため、
 * next_releaseを別々に管理し、タブも個別のマーケットインパクトを表示
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined, CalendarOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

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

import type {
  CnCaixinPmiData,
} from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義・定数
// =============================================================================

interface Props {
  data: CnCaixinPmiData | null
}

interface ChartDataPoint {
  date: string
  manufacturing: number | null
  services: number | null
}

const COLOR_MFG = '#722ed1'   // 紫（製造業）
const COLOR_SVC = '#eb2f96'   // ピンク（サービス業）

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

export default function CnCaixinPmiChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 製造業とサービス業のデータを日付で統合
  const chartData = useMemo((): ChartDataPoint[] => {
    if (!data) return []

    const mfgData = data.manufacturing?.data ?? []
    const svcData = data.services?.data ?? []

    // 日付をキーにマージ
    const dateMap = new Map<string, ChartDataPoint>()

    for (const item of mfgData) {
      dateMap.set(item.date, {
        date: item.date,
        manufacturing: item.value,
        services: null,
      })
    }

    for (const item of svcData) {
      const existing = dateMap.get(item.date)
      if (existing) {
        existing.services = item.value
      } else {
        dateMap.set(item.date, {
          date: item.date,
          manufacturing: null,
          services: item.value,
        })
      }
    }

    return Array.from(dateMap.values())
  }, [data])

  const sortedData = useSortedData(chartData)
  const filteredData = usePeriodFiltering(sortedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2017,
  })

  if (!data || (!data.manufacturing && !data.services)) {
    return (
      <div id="caixin-pmi">
        <LoadingChart title="Caixin PMI" />
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div id="caixin-pmi">
        <ChartContainer title="Caixin PMI">
          <NoDataMessage />
        </ChartContainer>
      </div>
    )
  }

  const latestMfg = data.manufacturing?.latest
  const latestSvc = data.services?.latest

  // 次回発表日: 製造業とサービス業で近い方を表示
  const nextReleaseMfg = data.next_release_manufacturing
  const nextReleaseSvc = data.next_release_services

  return (
    <div id="caixin-pmi">
      <ChartContainer
        title="Caixin PMI"
        showDataSource={true}
        dataSource="S&P Global / Caixin"
        sourceUrl="https://www.pmi.spglobal.com/Public/Release/PressReleases"
        handbookId="caixin-pmi"
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 最新値ボックス */}
                  <div style={{ ...LATEST_VALUE_BOX_STYLE, justifyContent: 'space-between', alignItems: 'center' }}>
                    {/* 左側: 最新値 */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                      <_LatestBox
                        label="製造業"
                        value={latestMfg?.value}
                        dateStr={latestMfg?.date}
                        color={COLOR_MFG}
                        hidden={hiddenSeries.has('manufacturing')}
                        onClick={() => handleLegendClick('manufacturing')}
                      />
                      <_LatestBox
                        label="サービス業"
                        value={latestSvc?.value}
                        dateStr={latestSvc?.date}
                        color={COLOR_SVC}
                        hidden={hiddenSeries.has('services')}
                        onClick={() => handleLegendClick('services')}
                      />
                    </div>
                    {/* 右側: 次回発表 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {nextReleaseMfg && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: TEXT_COLORS.secondary }}>
                          <CalendarOutlined />
                          <span>製造業: {nextReleaseMfg.date}{nextReleaseMfg.time_jst && ` ${nextReleaseMfg.time_jst} JST`}</span>
                        </div>
                      )}
                      {nextReleaseSvc && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: TEXT_COLORS.secondary }}>
                          <CalendarOutlined />
                          <span>サービス業: {nextReleaseSvc.date}{nextReleaseSvc.time_jst && ` ${nextReleaseSvc.time_jst} JST`}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=cn_caixin_manufacturing_pmi&s=cn_caixin_services_pmi', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 期間セレクター */}
                  <PeriodSelector
                    onPeriodChange={setCurrentPeriod}
                    selectedPeriod={currentPeriod}
                  />

                  {/* チャート */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'manufacturing', color: COLOR_MFG, name: '財新製造業PMI', hide: hiddenSeries.has('manufacturing') },
                      { dataKey: 'services', color: COLOR_SVC, name: '財新サービス業PMI', hide: hiddenSeries.has('services') },
                    ]}
                    xAxisFormatter={formatDateLabel}
                    yAxisFormatter={(v: number) => `${v}`}
                    yDomain={['dataMin - 1', 'dataMax + 1']}
                    tooltipLabelFormatter={formatDateFull}
                    tooltipValueFormatter={(v: number) => `${v.toFixed(1)}`}
                    showFiftyLine={true}
                    showZeroLine={false}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market-impact-manufacturing',
              label: 'マーケットインパクト（製造業）',
              children: (
                <MarketImpactTab indicatorId="cn_caixin_manufacturing_pmi" />
              ),
            },
            {
              key: 'market-impact-services',
              label: 'マーケットインパクト（サービス業）',
              children: (
                <MarketImpactTab indicatorId="cn_caixin_service_pmi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}

// 最新値ボックスのサブコンポーネント
function _LatestBox({
  label,
  value,
  dateStr,
  color,
  hidden,
  onClick,
}: {
  label: string
  value: number | null | undefined
  dateStr: string | undefined
  color: string
  hidden: boolean
  onClick: () => void
}) {
  return (
    <span
      onClick={onClick}
      style={{
        cursor: 'pointer',
        opacity: hidden ? 0.3 : 1,
        marginRight: 16,
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
      <span style={{ fontSize: 12, color: '#666' }}>
        {label}
        {dateStr && <span style={{ marginLeft: 4, fontSize: 10, color: '#999' }}>({formatDateFull(dateStr)})</span>}
      </span>
      <span style={{ fontSize: 18, fontWeight: 700, color }}>
        {value != null ? value.toFixed(1) : '—'}
      </span>
    </span>
  )
}
