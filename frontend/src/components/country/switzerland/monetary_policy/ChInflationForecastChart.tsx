/**
 * SNBインフレ見通しチャートコンポーネント
 *
 * SNBプレスリリースからのインフレ見通し画像を表示（最新分のみ）
 *
 * データソース:
 * - Swiss National Bank プレスリリース
 *
 * 発表スケジュール:
 * - 不定期（年4回程度、SNB金利決定と同時）
 * - 発表時刻: 08:30 チューリッヒ時間（16:30 JST）
 */
import { useState } from 'react'
import { Tabs, Card, Empty } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import MarketImpactTab from '../../../indicator/MarketImpactTab'

// 共通モジュールのインポート
import { formatDateLabel } from '../../usa/common/useChartData'
import { DARK_THEME } from '../../usa/common/chartConstants'

// 型定義
import type { ChInflationForecastData } from '../../../../hooks/useDashboardData'

interface ChInflationForecastChartProps {
  data: ChInflationForecastData | null
}

export default function ChInflationForecastChart({ data }: ChInflationForecastChartProps) {
  const [activeTab, setActiveTab] = useState<string>('forecast')

  // データがnullの場合はローディング表示
  if (data === null) {
    return <LoadingChart title="SNBインフレ見通し" />
  }

  const latest = data?.latest
  const hasData = !!latest

  if (!hasData) {
    return (
      <ChartContainer title="SNBインフレ見通し" showPeriodSelector={false} showDataSource={false}>
        <Empty description="データがありません" />
      </ChartContainer>
    )
  }

  // 次回発表日
  const nextRelease = data?.next_release

  return (
    <div id="ch-inflation-forecast-chart">
      <ChartContainer
        title="SNBインフレ見通し"
        showPeriodSelector={false}
        dataSource="Swiss National Bank"
        sourceUrl="https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy/decisions"
      >
        {/* 発表日と次回発表日 */}
        <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: DARK_THEME.textPrimary, fontSize: 14 }}>
            発表日: <strong>{formatDateLabel(latest.release_date)}</strong>
          </span>
          {nextRelease && (
            <span style={{ color: DARK_THEME.textSecondary, fontSize: 12, marginLeft: 'auto' }}>
              次回発表: {formatDateLabel(nextRelease.date)}
              {nextRelease.time_jst && ` ${nextRelease.time_jst} JST`}
            </span>
          )}
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'forecast',
              label: 'インフレ見通し',
              children: (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  {/* 条件付きインフレ見通し */}
                  {latest.forecast_image && (
                    <Card
                      size="small"
                      title="条件付きインフレ見通し (Conditional Inflation Forecast)"
                      style={{ backgroundColor: DARK_THEME.bgSecondary, border: `1px solid ${DARK_THEME.borderLight}` }}
                      headStyle={{ backgroundColor: DARK_THEME.bgTertiary, color: DARK_THEME.textPrimary, borderBottom: `1px solid ${DARK_THEME.borderLight}` }}
                      bodyStyle={{ padding: 16, backgroundColor: '#fff' }}
                    >
                      <img
                        src={latest.forecast_image}
                        alt="Conditional Inflation Forecast"
                        style={{
                          width: '100%',
                          maxWidth: 900,
                          height: 'auto',
                          display: 'block',
                          margin: '0 auto',
                        }}
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none'
                        }}
                      />
                    </Card>
                  )}

                  {/* 実績インフレ率 */}
                  {latest.observed_image && (
                    <Card
                      size="small"
                      title="実績インフレ率 (Observed Inflation)"
                      style={{ backgroundColor: DARK_THEME.bgSecondary, border: `1px solid ${DARK_THEME.borderLight}` }}
                      headStyle={{ backgroundColor: DARK_THEME.bgTertiary, color: DARK_THEME.textPrimary, borderBottom: `1px solid ${DARK_THEME.borderLight}` }}
                      bodyStyle={{ padding: 16, backgroundColor: '#fff' }}
                    >
                      <img
                        src={latest.observed_image}
                        alt="Observed Inflation"
                        style={{
                          width: '100%',
                          maxWidth: 900,
                          height: 'auto',
                          display: 'block',
                          margin: '0 auto',
                        }}
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none'
                        }}
                      />
                    </Card>
                  )}

                  {!latest.forecast_image && !latest.observed_image && (
                    <Empty description="画像データがありません" />
                  )}
                </div>
              ),
            },
            {
              key: 'market_impact',
              label: 'マーケットインパクト',
              children: <MarketImpactTab indicatorId="ch_snb_rate" />,
            },
          ]}
        />
      </ChartContainer>
    </div>
  )
}
