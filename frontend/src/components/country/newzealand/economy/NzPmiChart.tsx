/**
 * NZ PMI/PSI/PCIチャートコンポーネント
 *
 * データ:
 * - PMI: BusinessNZ Manufacturing PMI（製造業PMI・季節調整済み）
 * - PSI: BusinessNZ Performance of Services Index（サービス業PSI・季節調整済み）
 * - PCI: BusinessNZ/BNZ Performance of Composite Index（総合PCI・GDP加重・季節調整済み）
 *
 * データソース:
 * - BusinessNZ (https://businessnz.org.nz/)
 *
 * FMPマッピング:
 * - Business NZ PMI (econalpha_id: nz_pmi)
 * - Services NZ PSI (econalpha_id: nz_psi)
 * - Composite NZ PCI (econalpha_id: nz_pci)
 */
import { useState, useMemo } from 'react'
import { Tabs, Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'
import type { PeriodValue } from '../../../common/PeriodSelector'

import {
  usePeriodFiltering,
  useHiddenSeries,
} from '../../usa/common/useChartData'
import {
  NoDataMessage,
  LatestValueBox,
  StandardLineChart,
} from '../../usa/common/ChartComponents'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

import type { NzPmiData } from '../../../../hooks/useDashboardData'

// =============================================================================
// 型定義
// =============================================================================

interface NzPmiChartProps {
  pmi: NzPmiData | null
  psi: NzPmiData | null
  pci: NzPmiData | null
}

interface ChartDataPoint {
  date: string
  pmi: number | null
  psi: number | null
  pci: number | null
}

// タブ
type ActiveTab = 'timeseries' | 'market_impact_pmi' | 'market_impact_psi' | 'market_impact_pci'

// カラー設定
const COLORS = {
  pmi: '#2563eb',  // 青（製造業）
  psi: '#16a34a',  // 緑（サービス業）
  pci: '#dc2626',  // 赤（総合）
}

// =============================================================================
// 日付フォーマット
// =============================================================================

const formatMonthLabel = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}/${month}`
}

const formatMonthLabelJP = (dateStr: string): string => {
  if (!dateStr) return ''
  const [year, month] = dateStr.split('-')
  return `${year}年${parseInt(month, 10)}月`
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function NzPmiChart({ pmi, psi, pci }: NzPmiChartProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>('timeseries')
  const [currentPeriod, setCurrentPeriod] = useState<PeriodValue>('default')
  const { hiddenSeries, handleLegendClick } = useHiddenSeries()

  // 3系列を日付でマージ
  const mergedData = useMemo<ChartDataPoint[]>(() => {
    const dateMap: Record<string, ChartDataPoint> = {}

    if (pmi?.data) {
      for (const item of pmi.data) {
        if (!dateMap[item.date]) dateMap[item.date] = { date: item.date, pmi: null, psi: null, pci: null }
        dateMap[item.date].pmi = item.value
      }
    }
    if (psi?.data) {
      for (const item of psi.data) {
        if (!dateMap[item.date]) dateMap[item.date] = { date: item.date, pmi: null, psi: null, pci: null }
        dateMap[item.date].psi = item.value
      }
    }
    if (pci?.data) {
      for (const item of pci.data) {
        if (!dateMap[item.date]) dateMap[item.date] = { date: item.date, pmi: null, psi: null, pci: null }
        dateMap[item.date].pci = item.value
      }
    }

    return Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date))
  }, [pmi, psi, pci])

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(mergedData, {
    selectedPeriod: currentPeriod,
    defaultStartYear: 2015,
  })

  const hasData = mergedData.length > 0

  // ローディング状態（全てnullの場合）
  if (pmi === null && psi === null && pci === null) {
    return <LoadingChart title="PMI / PSI / PCI" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="PMI / PSI / PCI" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  // 最新値（各指標の最後のデータ点）
  const latestPmi = pmi?.latest
  const latestPsi = psi?.latest
  const latestPci = pci?.latest

  // 次回発表日（PMIを基準。各指標は別日なので最も近いものを表示）
  const nextReleasePmi = pmi?.next_release ?? undefined
  const nextReleasePsi = psi?.next_release ?? undefined
  const nextReleasePci = pci?.next_release ?? undefined

  return (
    <div id="nz-pmi">
      <ChartContainer
        title="PMI / PSI / PCI"
        showPeriodSelector={false}
        showDataSource={true}
        dataSource="BusinessNZ"
        sourceUrl="https://businessnz.org.nz/business-issues/manufacturing"
      >
        {/* 最新値表示（3指標） */}
        <LatestValueBox
          items={[
            {
              label: '製造業PMI',
              value: latestPmi?.value,
              color: COLORS.pmi,
              format: 'number',
              decimals: 1,
            },
            {
              label: 'サービス業PSI',
              value: latestPsi?.value,
              color: COLORS.psi,
              format: 'number',
              decimals: 1,
            },
            {
              label: '総合PCI',
              value: latestPci?.value,
              color: COLORS.pci,
              format: 'number',
              decimals: 1,
            },
          ]}
          date={latestPci?.date ?? latestPsi?.date ?? latestPmi?.date}
          dateFormatter={formatMonthLabelJP}
          nextRelease={nextReleasePmi ?? nextReleasePsi ?? nextReleasePci}
        />

        {/* タブ切替 */}
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as ActiveTab)}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'timeseries',
              label: '時系列',
              children: (
                <>
                  {/* 期間選択 + データ比較ボタン */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <PeriodSelector onPeriodChange={setCurrentPeriod} selectedPeriod={currentPeriod} />
                    <Tooltip title="比較ページを開く">
                      <Button
                        icon={<AreaChartOutlined />}
                        onClick={() => window.open('/compare?s=nz_pmi&s=nz_psi&s=nz_pci', '_blank')}
                      >
                        データ比較
                      </Button>
                    </Tooltip>
                  </div>

                  {/* 折れ線グラフ（3系列） */}
                  <StandardLineChart
                    data={filteredData}
                    lines={[
                      { dataKey: 'pmi', color: COLORS.pmi, name: '製造業PMI', hide: hiddenSeries.has('pmi') },
                      { dataKey: 'psi', color: COLORS.psi, name: 'サービス業PSI', hide: hiddenSeries.has('psi') },
                      { dataKey: 'pci', color: COLORS.pci, name: '総合PCI', hide: hiddenSeries.has('pci') },
                    ]}
                    yAxisFormatter={(v) => `${v}`}
                    yDomain={['dataMin - 2', 'dataMax + 2']}
                    showZeroLine={false}
                    xAxisFormatter={formatMonthLabel}
                    tooltipLabelFormatter={formatMonthLabelJP}
                    tooltipValueFormatter={(v) => `${v.toFixed(1)}`}
                    onLegendClick={handleLegendClick}
                  />
                </>
              ),
            },
            {
              key: 'market_impact_pmi',
              label: 'マーケットインパクト（PMI）',
              children: (
                <MarketImpactTab indicatorId="nz_pmi" />
              ),
            },
            {
              key: 'market_impact_psi',
              label: 'マーケットインパクト（PSI）',
              children: (
                <MarketImpactTab indicatorId="nz_psi" />
              ),
            },
            {
              key: 'market_impact_pci',
              label: 'マーケットインパクト（PCI）',
              children: (
                <MarketImpactTab indicatorId="nz_pci" />
              ),
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
