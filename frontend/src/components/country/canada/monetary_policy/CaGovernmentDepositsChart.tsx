/**
 * カナダ政府預金（Government of Canada Canadian dollar deposits）チャートコンポーネント
 *
 * TGA相当の指標
 * - Total: GOCCADDEPTOT - 政府預金合計
 * - BoC: GOCCADDEPBOC - BOC保有分
 * - Auction Participants: GOCCADDEPAP - オークション参加者保有分
 *
 * 政府預金の増減＝民間資金の吸収/放出として、短期資金環境の説明変数
 *
 * データソース:
 * - Bank of Canada Valet API
 *
 * 発表スケジュール:
 * - 週次: 金曜 14:30 ET
 */
import { useState, useMemo } from 'react'
import { Tooltip as RechartsTooltip } from 'recharts'
import { Button, Tooltip } from 'antd'
import { AreaChartOutlined } from '@ant-design/icons'
import ChartContainer from '../../../common/ChartContainer'
import ZoomableChart from '../../../common/ZoomableChart'
import LoadingChart from '../../../common/LoadingChart'
import PeriodSelector from '../../../common/PeriodSelector'

// 共通モジュールのインポート
import { usePeriodFiltering, formatDateLabel, formatDateLabelFull, type PeriodType } from '../../usa/common/useChartData'
import { NoDataMessage, SimpleLatestValueBox, ViewModeButtonGroup } from '../../usa/common/ChartComponents'
import { DARK_THEME } from '../../usa/common/chartConstants'

// 型定義
import type { CaGovernmentDepositsData } from '../../../../hooks/useDashboardData'

interface CaGovernmentDepositsChartProps {
  data: CaGovernmentDepositsData | null
}

interface ChartDataItem {
  date: string
  value: number | null
  total: number | null
  boc: number | null
  ap: number | null
  [key: string]: string | number | null | undefined
}

type ViewMode = 'total' | 'breakdown'

export default function CaGovernmentDepositsChart({ data }: CaGovernmentDepositsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<PeriodType>(2)
  const [viewMode, setViewMode] = useState<ViewMode>('total')

  // propsのデータをチャート用に変換
  const chartData = useMemo<ChartDataItem[]>(() => {
    if (!data?.data || data.data.length === 0) return []

    const formattedData: ChartDataItem[] = data.data.map((item) => ({
      date: item.date,
      value: item.total,
      total: item.total,
      boc: item.boc,
      ap: item.ap,
    }))

    // 日付でソート（古い順）
    formattedData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    return formattedData
  }, [data])

  const formatValue = (value: number) => {
    // 十億CAD単位で表示
    return `${(value / 1000).toFixed(1)}B`
  }

  const formatTooltipValue = (value: number) => {
    // ツールチップでは詳細に表示
    return `${value.toLocaleString()} M CAD`
  }

  // 期間フィルタリング
  const filteredData = usePeriodFiltering(chartData, {
    selectedPeriod,
    defaultStartYear: 2015,
  })

  const hasData = chartData.length > 0

  // 最新値を取得
  const latestValue = data?.latest

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="政府預金（Government Deposits）" />
  }

  if (!hasData) {
    return (
      <ChartContainer title="政府預金（Government Deposits）" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="ca-government-deposits-chart">
      <ChartContainer
        title="政府預金（Government Deposits）"
        showPeriodSelector={false}
        dataSource="Bank of Canada"
        sourceUrl="https://www.bankofcanada.ca/rates/indicators/market-operations-indicators/"
      >
        {/* 最新値表示 */}
        <SimpleLatestValueBox
          label="最新残高（合計）"
          value={latestValue?.total}
          valueColor="#8B5CF6"
          date={latestValue?.date}
          format="number"
          decimals={0}
          unit="M CAD"
        />

        {/* ViewMode切り替え */}
        <div style={{ marginBottom: 12 }}>
          <ViewModeButtonGroup
            options={[
              { mode: 'total', label: '合計' },
              { mode: 'breakdown', label: '内訳' },
            ]}
            currentMode={viewMode}
            onChange={(v) => setViewMode(v as ViewMode)}
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <PeriodSelector onPeriodChange={setSelectedPeriod} selectedPeriod={selectedPeriod} />
          <Tooltip title="比較ページを開く">
            <Button
              icon={<AreaChartOutlined />}
              onClick={() => window.open('/compare?s=ca_government_deposits', '_blank')}
            >
              データ比較
            </Button>
          </Tooltip>
        </div>

        {viewMode === 'total' ? (
          <ZoomableChart
            key="total-view"
            data={filteredData}
            dataKey="total"
            color="#8B5CF6"
            name="政府預金（合計）"
            height={450}
            tickFormatter={formatValue}
            xAxisTickFormatter={formatDateLabel}
            enableDynamicTicks={true}
            showZeroLine={false}
            showFiftyLine={false}
            connectNulls={true}
            hideLegend={true}
            showDefaultTooltip={false}
            domain={['dataMin - 5000', 'dataMax + 5000']}
          >
            <RechartsTooltip
              content={({ active, payload, label }) => {
                if (!active || !payload || payload.length === 0) return null
                return (
                  <div
                    style={{
                      backgroundColor: DARK_THEME.bgTertiary,
                      border: `1px solid ${DARK_THEME.borderLight}`,
                      borderRadius: 8,
                      padding: '12px 16px',
                      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                    }}
                  >
                    <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
                      {formatDateLabelFull(String(label))}
                    </div>
                    {payload.map((item, index) => (
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
                              backgroundColor: item.color || '#8B5CF6',
                              marginRight: 6,
                            }}
                          />
                          {item.name}
                        </span>
                        <span style={{ fontWeight: 500, color: item.color || '#8B5CF6' }}>
                          {formatTooltipValue(item.value as number)}
                        </span>
                      </div>
                    ))}
                  </div>
                )
              }}
            />
          </ZoomableChart>
        ) : (
          <ZoomableChart
            key="breakdown-view"
            data={filteredData}
            dataKey="boc"
            color="#3B82F6"
            name="BOC保有分"
            additionalLines={[
              { dataKey: 'ap', color: '#F59E0B', name: 'オークション参加者' },
            ]}
            height={450}
            tickFormatter={formatValue}
            xAxisTickFormatter={formatDateLabel}
            enableDynamicTicks={true}
            showZeroLine={false}
            showFiftyLine={false}
            connectNulls={true}
            hideLegend={false}
            showDefaultTooltip={false}
            domain={['dataMin - 5000', 'dataMax + 5000']}
          >
            <RechartsTooltip
              content={({ active, payload, label }) => {
                if (!active || !payload || payload.length === 0) return null
                return (
                  <div
                    style={{
                      backgroundColor: DARK_THEME.bgTertiary,
                      border: `1px solid ${DARK_THEME.borderLight}`,
                      borderRadius: 8,
                      padding: '12px 16px',
                      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                    }}
                  >
                    <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: 14, color: DARK_THEME.textPrimary }}>
                      {formatDateLabelFull(String(label))}
                    </div>
                    {payload.map((item, index) => (
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
                              backgroundColor: item.color || '#3B82F6',
                              marginRight: 6,
                            }}
                          />
                          {item.name}
                        </span>
                        <span style={{ fontWeight: 500, color: item.color || '#3B82F6' }}>
                          {formatTooltipValue(item.value as number)}
                        </span>
                      </div>
                    ))}
                  </div>
                )
              }}
            />
          </ZoomableChart>
        )}
      </ChartContainer>
    </div>
  )
}
