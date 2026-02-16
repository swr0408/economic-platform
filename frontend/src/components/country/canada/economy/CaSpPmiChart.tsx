/**
 * カナダ S&P Global PMI チャートコンポーネント
 *
 * 製造業PMI、サービス業PMI、総合PMIを表示
 *
 * データソース:
 * - S&P Global
 *
 * 発表スケジュール:
 * - 速報値: 毎月第3週（23日前後）
 * - 確報値: 毎月第1週（1日前後）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { CaSpPmiData } from '../../../../hooks/useDashboardData'

import { CHART_COLORS, LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'
import {
  usePeriodFiltering,
  useHiddenSeries,
  type PeriodType,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'

import MarketImpactTab from '../../../indicator/MarketImpactTab'

// カラー設定
const COLORS = {
  manufacturing: CHART_COLORS.primary,  // 青
  services: CHART_COLORS.positive,       // 緑
  composite: CHART_COLORS.purple,        // 紫
}

interface CaSpPmiChartProps {
  data: CaSpPmiData | null
}

export default function CaSpPmiChart({ data }: CaSpPmiChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>('default')
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 3系列のデータをマージして1つのチャートデータに変換
  const chartData = useMemo(() => {
    if (!data) return []

    const mfgData = data.manufacturing?.data || []
    const svcData = data.services?.data || []
    const cmpData = data.composite?.data || []

    const allDates = new Set<string>()
    mfgData.forEach((d) => allDates.add(d.date))
    svcData.forEach((d) => allDates.add(d.date))
    cmpData.forEach((d) => allDates.add(d.date))

    const sortedDates = Array.from(allDates).sort(
      (a, b) => new Date(a).getTime() - new Date(b).getTime()
    )

    const mfgMap = new Map(mfgData.map((d) => [d.date, d.value]))
    const svcMap = new Map(svcData.map((d) => [d.date, d.value]))
    const cmpMap = new Map(cmpData.map((d) => [d.date, d.value]))

    return sortedDates.map((date) => ({
      date,
      manufacturing: mfgMap.get(date) ?? null,
      services: svcMap.get(date) ?? null,
      composite: cmpMap.get(date) ?? null,
    }))
  }, [data])

  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2020,
  })

  const hasData = chartData.length > 0

  if (data === null) {
    return <LoadingChart title="S&P Global PMI" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="S&P Global PMI" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  const mfgLatest = data.manufacturing?.latest
  const svcLatest = data.services?.latest
  const cmpLatest = data.composite?.latest

  return (
    <div id="ca-sp-pmi-chart">
      <ChartContainer
        title="S&P Global PMI"
        showPeriodSelector={false}
        dataSource="S&P Global"
        sourceUrl="https://www.pmi.spglobal.com/Public/Release/PressReleases"
      >
        {/* 最新値表示（3系列） */}
        <div style={LATEST_VALUE_BOX_STYLE}>
          {/* 製造業PMI */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.manufacturing,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>製造業</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.manufacturing }}>
              {mfgLatest?.value?.toFixed(1) ?? '-'}
            </span>
          </div>

          {/* サービス業PMI */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.services,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>サービス業</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.services }}>
              {svcLatest?.value?.toFixed(1) ?? '-'}
            </span>
          </div>

          {/* 総合PMI */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 12,
                height: 12,
                backgroundColor: COLORS.composite,
                borderRadius: 2,
              }}
            />
            <span style={{ fontSize: 12, color: '#a0a0a0' }}>総合</span>
            <span style={{ fontSize: 18, fontWeight: 'bold', color: COLORS.composite }}>
              {cmpLatest?.value?.toFixed(1) ?? '-'}
            </span>
          </div>

          {/* 日付・次回発表情報 */}
          <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'flex-end', fontSize: 11, color: '#8c8c8c' }}>
            {mfgLatest?.date && <div>{mfgLatest.date}</div>}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
                    <Tooltip title="比較ページを開く（S&P PMI）">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=ca_manufacturing_pmi&s=ca_service_pmi&s=ca_composite_pmi', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'manufacturing', color: COLORS.manufacturing, name: '製造業PMI', hide: hiddenSeries.has('manufacturing') },
                      { dataKey: 'services', color: COLORS.services, name: 'サービス業PMI', hide: hiddenSeries.has('services') },
                      { dataKey: 'composite', color: COLORS.composite, name: '総合PMI', hide: hiddenSeries.has('composite') },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    tooltipValueFormatter={(v) => v.toFixed(1)}
                    showZeroLine={false}
                    showFiftyLine={true}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market-impact',
              label: 'マーケットインパクト',
              children: (
                <MarketImpactTab indicatorId="ca_manufacturing_pmi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
