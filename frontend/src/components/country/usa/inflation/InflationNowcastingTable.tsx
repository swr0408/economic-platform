/**
 * インフレーションナウキャスティングテーブルコンポーネント
 *
 * Cleveland FedのInflation Nowcasting予測データを表示
 * - CPI, Core CPI, PCE, Core PCE の月次予測値
 * - MoM（前月比）とYoY（前年比）の切り替え
 *
 * データソース: Cleveland Fed
 * https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting
 */
import { useState, useMemo } from 'react'
import { Segmented } from 'antd'
import ChartContainer from '../../../common/ChartContainer'
import LoadingChart from '../../../common/LoadingChart'
import type { InflationNowcastingData } from '../../../../hooks/useDashboardData'

// 共通モジュールのインポート
import { NoDataMessage } from '../common/ChartComponents'
import { DARK_THEME, TEXT_COLORS } from '../common/chartConstants'

// =============================================================================
// 型定義
// =============================================================================

interface InflationNowcastingTableProps {
  nowcastingData: InflationNowcastingData | null
}

type ViewMode = 'mom' | 'yoy'

// カラー設定
const COLORS = {
  cpi: '#3b82f6',       // CPI（青）
  core_cpi: '#10b981',  // コアCPI（緑）
  pce: '#ef4444',       // PCE（赤）
  core_pce: '#a855f7',  // コアPCE（紫）
}

// 項目の日本語名
const LABELS: Record<string, string> = {
  cpi: 'CPI',
  core_cpi: 'コアCPI',
  pce: 'PCE',
  core_pce: 'コアPCE',
}

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function InflationNowcastingTable({ nowcastingData }: InflationNowcastingTableProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('mom')

  // 表示するデータを選択
  const displayData = useMemo(() => {
    if (!nowcastingData) return []
    return viewMode === 'mom' ? nowcastingData.monthly_mom : nowcastingData.monthly_yoy
  }, [nowcastingData, viewMode])

  // 最新データ（最初の行）
  const latestData = useMemo(() => {
    if (displayData.length === 0) return null
    return displayData[0]
  }, [displayData])

  const hasData = displayData.length > 0

  // ローディング状態
  if (nowcastingData === null) {
    return <LoadingChart title="Inflation Nowcasting" />
  }

  // データなし状態
  if (!hasData) {
    return (
      <ChartContainer title="Inflation Nowcasting" showPeriodSelector={false} showDataSource={false}>
        <NoDataMessage />
      </ChartContainer>
    )
  }

  return (
    <div id="inflation-nowcasting">
      <ChartContainer
        title="インフレーションナウキャスティング"
        showPeriodSelector={false}
        dataSource="Cleveland Fed"
        sourceUrl="https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting"
      >
        {/* 最新値表示 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 12,
            marginBottom: 16,
            padding: 12,
            backgroundColor: DARK_THEME.bgSecondary,
            borderRadius: 8,
            border: `1px solid ${DARK_THEME.border}`,
          }}
        >
          {(['cpi', 'core_cpi', 'pce', 'core_pce'] as const).map((key) => {
            const value = latestData?.[key]
            return (
              <div key={key} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 11, color: TEXT_COLORS.tertiary, marginBottom: 4 }}>
                  {LABELS[key]}
                </div>
                <div style={{ fontSize: 20, fontWeight: 'bold', color: COLORS[key] }}>
                  {value != null ? `${value.toFixed(2)}%` : '-'}
                </div>
              </div>
            )
          })}
          <div style={{ gridColumn: '1 / -1', textAlign: 'right', fontSize: 11, color: TEXT_COLORS.quaternary }}>
            {latestData?.date || '-'}（{viewMode === 'mom' ? '前月比' : '前年比'}）
          </div>
        </div>

        {/* MoM/YoY切り替え */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
          <Segmented
            options={[
              { label: '前月比', value: 'mom' },
              { label: '前年比', value: 'yoy' },
            ]}
            value={viewMode}
            onChange={(value) => setViewMode(value as ViewMode)}
          />
        </div>

        {/* テーブル */}
        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: 13,
              color: DARK_THEME.textPrimary,
            }}
          >
            <thead>
              <tr style={{ backgroundColor: DARK_THEME.bgTertiary }}>
                <th
                  style={{
                    padding: '10px 12px',
                    borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                    fontWeight: 'bold',
                    textAlign: 'left',
                    minWidth: 120,
                  }}
                >
                  期間
                </th>
                <th
                  style={{
                    padding: '10px 12px',
                    borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                    fontWeight: 'bold',
                    textAlign: 'center',
                    color: COLORS.cpi,
                  }}
                >
                  {LABELS.cpi}
                </th>
                <th
                  style={{
                    padding: '10px 12px',
                    borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                    fontWeight: 'bold',
                    textAlign: 'center',
                    color: COLORS.core_cpi,
                  }}
                >
                  {LABELS.core_cpi}
                </th>
                <th
                  style={{
                    padding: '10px 12px',
                    borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                    fontWeight: 'bold',
                    textAlign: 'center',
                    color: COLORS.pce,
                  }}
                >
                  {LABELS.pce}
                </th>
                <th
                  style={{
                    padding: '10px 12px',
                    borderBottom: `2px solid ${DARK_THEME.borderLight}`,
                    fontWeight: 'bold',
                    textAlign: 'center',
                    color: COLORS.core_pce,
                  }}
                >
                  {LABELS.core_pce}
                </th>
              </tr>
            </thead>
            <tbody>
              {displayData.map((row, index) => (
                <tr
                  key={row.date}
                  style={{
                    backgroundColor: index === 0 ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                  }}
                >
                  <td
                    style={{
                      padding: '8px 12px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      fontWeight: index === 0 ? 'bold' : 'normal',
                    }}
                  >
                    {row.date}
                  </td>
                  <td
                    style={{
                      padding: '8px 12px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      textAlign: 'center',
                      color: row.cpi != null ? COLORS.cpi : TEXT_COLORS.quaternary,
                    }}
                  >
                    {row.cpi != null ? `${row.cpi.toFixed(2)}%` : '-'}
                  </td>
                  <td
                    style={{
                      padding: '8px 12px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      textAlign: 'center',
                      color: row.core_cpi != null ? COLORS.core_cpi : TEXT_COLORS.quaternary,
                    }}
                  >
                    {row.core_cpi != null ? `${row.core_cpi.toFixed(2)}%` : '-'}
                  </td>
                  <td
                    style={{
                      padding: '8px 12px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      textAlign: 'center',
                      color: row.pce != null ? COLORS.pce : TEXT_COLORS.quaternary,
                    }}
                  >
                    {row.pce != null ? `${row.pce.toFixed(2)}%` : '-'}
                  </td>
                  <td
                    style={{
                      padding: '8px 12px',
                      borderBottom: `1px solid ${DARK_THEME.border}`,
                      textAlign: 'center',
                      color: row.core_pce != null ? COLORS.core_pce : TEXT_COLORS.quaternary,
                    }}
                  >
                    {row.core_pce != null ? `${row.core_pce.toFixed(2)}%` : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartContainer>
    </div>
  )
}
