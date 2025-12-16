import { Spin, Alert, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useUSAPolicyDashboard } from '../../../hooks/useDashboardData'
import PolicyRateChart from './monetary_policy/PolicyRateChart'
import TermPremiumChart from './monetary_policy/TermPremiumChart'
import CMEFedWatchChart from './monetary_policy/CMEFedWatchChart'
import FOMCProjectionsChart from './monetary_policy/FOMCProjectionsChart'
import FOMCTable1Chart from './monetary_policy/FOMCTable1Chart'

/**
 * 米国金融政策チャート群
 *
 * バッチAPIで全データを一括取得し、各チャートコンポーネントにpropsで渡す
 * これにより7-8リクエスト → 1リクエストに削減し、ページ読み込みを高速化
 */
export default function USAPolicyCharts() {
  const { data, isLoading, error, refetch, isFetching } = useUSAPolicyDashboard()

  // ローディング状態
  if (isLoading) {
    return <PolicyChartsSkeleton />
  }

  // エラー状態
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
      {/* 最終更新時刻 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
          fontSize: 12,
          color: '#666',
        }}
      >
        <span>
          {data?.last_updated && (
            <>
              最終更新: {new Date(data.last_updated).toLocaleString('ja-JP')}
              {data.cached && (
                <span style={{ marginLeft: 8, color: '#52c41a' }}>(キャッシュ)</span>
              )}
            </>
          )}
        </span>
        <Button
          icon={<ReloadOutlined spin={isFetching} />}
          size="small"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          更新
        </Button>
      </div>

      {/* Federal Funds Target Rate Chart */}
      <div id="policy-rate">
        <PolicyRateChart data={dashboardData?.policy_rate ?? null} />
      </div>

      {/* CME FedWatch Tool */}
      <div id="fed-watch">
        <CMEFedWatchChart screenshotUrl={dashboardData?.fedwatch_screenshot_url ?? null} />
      </div>

      {/* ACM Term Premium Chart */}
      <div id="term-premium">
        <TermPremiumChart
          data={dashboardData?.term_premium ?? null}
          kwData={dashboardData?.kw_term_premium ?? null}
        />
      </div>

      {/* FOMC Dot Plot */}
      <div id="dot-plot">
        <FOMCProjectionsChart sepDates={dashboardData?.sep_dates ?? null} />
      </div>

      {/* FOMC Economic Projections Table 1 */}
      <div id="fomc-projections">
        <FOMCTable1Chart sepDates={dashboardData?.sep_dates ?? null} />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
function PolicyChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>金融政策データを読み込み中...</div>
      </div>
    </div>
  )
}
