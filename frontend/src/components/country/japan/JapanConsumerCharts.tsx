import { Spin } from 'antd'
import ConsumerSentimentChart from './consumer/ConsumerSentimentChart'
import BOJCAIChart from './consumer/BOJCAIChart'
import EconomyWatcherChart from './consumer/EconomyWatcherChart'

/**
 * 日本消費チャート群
 *
 * 消費関連のチャートを表示
 */
export default function JapanConsumerCharts() {
  return (
    <div className="country-chart-stack">
      {/* 消費動向調査（消費者態度指数） */}
      <div id="consumer-sentiment">
        <ConsumerSentimentChart />
      </div>

      {/* 消費活動指数（旅行収支調整前） */}
      <div id="boj-cai">
        <BOJCAIChart />
      </div>

      {/* 景気ウォッチャー調査（現状判断DI・先行き判断DI タブ切り替え） */}
      <div id="economy-watcher">
        <EconomyWatcherChart />
      </div>
    </div>
  )
}

/**
 * スケルトンローダー
 * データ取得中に表示される骨組み
 */
export function ConsumerChartsSkeleton() {
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
        <div style={{ marginTop: 16, color: '#666' }}>消費指標データを読み込み中...</div>
      </div>
    </div>
  )
}
