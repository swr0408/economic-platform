/**
 * 日本雇用チャートコンポーネント群
 *
 * ダッシュボードで使用される日本雇用関連チャートをまとめたコンポーネント
 */

import { Spin, Alert, Button } from 'antd'
import { useJapanEmploymentDashboard } from '../../../hooks/useDashboardData'
import ScheduledWageChart from './employment/ScheduledWageChart'
import ScheduledWageCommonChart from './employment/ScheduledWageCommonChart'
import EmploymentTypeChart from './employment/EmploymentTypeChart'
import UnemploymentChart from './employment/UnemploymentChart'
import JobOffersRatioChart from './employment/JobOffersRatioChart'

/**
 * 日本雇用チャート群
 *
 * バッチAPIで雇用データを一括取得し、各チャートコンポーネントにpropsで渡す
 */
export default function JapanEmploymentCharts() {
  const { data, isLoading, error, refetch } = useJapanEmploymentDashboard()

  // エラー状態（ダッシュボードAPI全体のエラー）
  if (error) {
    return (
      <Alert
        type="error"
        message="データの取得に失敗しました"
        description={error.message}
        action={
          <Button size="small" onClick={() => refetch()}>
            再試行
          </Button>
        }
        style={{ marginBottom: 24 }}
      />
    )
  }

  const dashboardData = data?.data

  return (
    <div className="country-chart-stack">
      {/* 所定内給与（e-Stat版） */}
      <div id="scheduled-wage">
        <ScheduledWageChart
          data={isLoading ? null : (dashboardData?.scheduled_wage ?? null)}
        />
      </div>

      {/* 所定内給与（共通事業所版） */}
      <div id="scheduled-wage-common">
        <ScheduledWageCommonChart
          data={isLoading ? null : (dashboardData?.scheduled_wage_common ?? null)}
        />
      </div>

      {/* 雇用形態別労働者過不足判断D.I. */}
      <div id="employment-type">
        <EmploymentTypeChart
          data={isLoading ? null : (dashboardData?.employment_type ?? null)}
        />
      </div>

      {/* 完全失業率 */}
      <div id="unemployment">
        <UnemploymentChart
          data={isLoading ? null : (dashboardData?.unemployment ?? null)}
        />
      </div>

      {/* 有効求人倍率 */}
      <div id="job-offers-ratio">
        <JobOffersRatioChart
          data={isLoading ? null : (dashboardData?.job_offers_ratio ?? null)}
        />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
export function EmploymentChartsSkeleton() {
  return (
    <div className="country-chart-stack">
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 400,
          background: '#fafafa',
          borderRadius: 12,
        }}
      >
        <Spin size="large" />
        <div style={{ marginTop: 16, color: '#666' }}>雇用指標データを読み込み中...</div>
      </div>
    </div>
  )
}
