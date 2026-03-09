/**
 * スイスPMIチャートコンポーネント
 *
 * procure.chから製造業・サービス業PMIを取得し表示
 *
 * データ:
 * - 製造業PMI (Manufacturing PMI)
 * - サービス業PMI (Services PMI)
 *
 * データソース:
 * - procure.ch (Swiss Procurement Association)
 *
 * 発表スケジュール:
 * - 月次（毎月第一営業日）
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector, { type PeriodValue } from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import { LATEST_VALUE_BOX_STYLE } from '../../usa/common/chartConstants'

// マーケットインパクト関連
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { CHPmiData } from '../../../../hooks/useDashboardData'

interface ChPmiChartProps {
  data: CHPmiData | null
}

interface ChartDataPoint {
  date: string
  manufacturing: number | null
  services: number | null
  [key: string]: unknown
}

// グラフの色
const COLORS = {
  manufacturing: '#DC143C', // スイス赤
  services: '#1890ff', // 青
}

export default function ChPmiChart({ data }: ChPmiChartProps) {
  const [activeTab, setActiveTab] = useState<string>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>(10)
  // 凡例クリックで非表示にするシリーズを管理
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // propsのデータをチャート用に変換（両データをマージ）
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!data) return []

    const dateMap: Record<string, ChartDataPoint> = {}

    // 製造業データをマージ
    data.manufacturing_data?.forEach((item) => {
      if (!dateMap[item.date]) {
        dateMap[item.date] = {
          date: item.date,
          manufacturing: null,
          services: null,
        }
      }
      dateMap[item.date].manufacturing = item.value
    })

    // サービス業データをマージ
    data.services_data?.forEach((item) => {
      if (!dateMap[item.date]) {
        dateMap[item.date] = {
          date: item.date,
          manufacturing: null,
          services: null,
        }
      }
      dateMap[item.date].services = item.value
    })

    // 日付順にソート
    return Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2018,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestManufacturing = data?.latest_manufacturing
  const latestServices = data?.latest_services

  if (data === null) {
    return <LoadingChart title="PMI" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="PMI" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // データ比較用のoverlayConfig ID
  const getCompareUrl = () => {
    return '/compare?s=ch_pmi_manufacturing&s=ch_pmi_services'
  }

  return (
    <div id="ch-pmi-chart">
      <ChartContainer
        title="PMI（購買担当者景気指数）"
        showPeriodSelector={false}
        dataSource="procure.ch"
        sourceUrl="https://www.procure.ch/magazin/themen/marktdaten"
      >
        {/* 最新値表示（2系列） */}
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
              {latestManufacturing?.value?.toFixed(1) ?? '-'}
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
              {latestServices?.value?.toFixed(1) ?? '-'}
            </span>
          </div>

          {/* 日付・次回発表情報（右側に配置） */}
          <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'flex-end', fontSize: 11, color: '#8c8c8c' }}>
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
                  {/* 期間セレクター */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open(getCompareUrl(), '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 製造業・サービス業PMI（凡例クリックで表示切替） */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'manufacturing', color: COLORS.manufacturing, name: '製造業PMI', hide: hiddenSeries.has('manufacturing') },
                      { dataKey: 'services', color: COLORS.services, name: 'サービス業PMI', hide: hiddenSeries.has('services') },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}`}
                    yDomain={['dataMin - 2', 'dataMax + 2']}
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
                <MarketImpactTab indicatorId="ch_pmi" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
