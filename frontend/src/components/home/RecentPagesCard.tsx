/**
 * ホーム画面 - 最近見たページカード
 *
 * localStorage から履歴を読み込んで表示する。
 * ページ遷移時の記録は useRecentPageTracker (MainLayout) 側で行う。
 */
import { useEffect, useState } from 'react'
import { Card, Typography, Empty, Button } from 'antd'
import { ClockCircleOutlined, DeleteOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import {
  getRecentPages,
  clearRecentPages,
  type RecentPageEntry,
} from '../../utils/recentPages'

const { Text } = Typography

const colors = {
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
}

function formatRelativeTime(viewedAt: number): string {
  const diffMs = Date.now() - viewedAt
  const sec = Math.floor(diffMs / 1000)
  if (sec < 60) return 'たった今'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}分前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}時間前`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day}日前`
  const month = Math.floor(day / 30)
  if (month < 12) return `${month}ヶ月前`
  return `${Math.floor(month / 12)}年前`
}

function RecentPagesCard() {
  const [entries, setEntries] = useState<RecentPageEntry[]>(() => getRecentPages())

  useEffect(() => {
    const refresh = () => setEntries(getRecentPages())
    // 同じタブ内の変更
    window.addEventListener('econalpha:recent-pages-changed', refresh)
    // 他のタブからの変更
    window.addEventListener('storage', refresh)
    return () => {
      window.removeEventListener('econalpha:recent-pages-changed', refresh)
      window.removeEventListener('storage', refresh)
    }
  }, [])

  const handleClear = () => {
    clearRecentPages()
  }

  return (
    <Card
      style={{
        background: colors.bgSecondary,
        border: `1px solid ${colors.border}`,
      }}
      styles={{ body: { padding: 16 } }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ClockCircleOutlined style={{ color: colors.accent }} />
          <Text strong style={{ color: colors.textPrimary, fontSize: 14 }}>
            最近見たページ
          </Text>
        </div>
        {entries.length > 0 && (
          <Button
            type="text"
            size="small"
            icon={<DeleteOutlined />}
            onClick={handleClear}
            style={{ color: colors.textTertiary, fontSize: 12 }}
          >
            クリア
          </Button>
        )}
      </div>

      {entries.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Text style={{ color: colors.textTertiary, fontSize: 12 }}>
              ページを閲覧すると、ここに履歴が表示されます
            </Text>
          }
          style={{ margin: '16px 0' }}
        />
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 8,
          }}
        >
          {entries.map((entry) => (
            <Link
              key={entry.path}
              to={entry.path}
              style={{ textDecoration: 'none' }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 8,
                  padding: '10px 12px',
                  background: colors.bgTertiary,
                  borderRadius: 8,
                  border: `1px solid transparent`,
                  transition: 'border-color 0.15s ease',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = colors.accent
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'transparent'
                }}
              >
                <Text
                  style={{
                    color: colors.textPrimary,
                    fontSize: 13,
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {entry.title}
                </Text>
                <Text
                  style={{
                    color: colors.textTertiary,
                    fontSize: 11,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {formatRelativeTime(entry.viewedAt)}
                </Text>
              </div>
            </Link>
          ))}
        </div>
      )}
    </Card>
  )
}

export default RecentPagesCard
