import { useState, useEffect } from 'react'
import { Typography, Button, Tag, Space, Spin, Image } from 'antd'
import { CloseOutlined, BookOutlined, LinkOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  HANDBOOK_MAP,
  HANDBOOK_COUNTRY_LABELS,
  HANDBOOK_CATEGORY_LABELS,
  type HandbookEntry,
} from '../../content/handbookRegistry'

const { Text, Title } = Typography

const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  accentHover: '#34d399',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
  borderLight: '#475569',
}

interface HandbookDrawerProps {
  /** 表示する指標ID（nullで非表示） */
  indicatorId: string | null
  /** 閉じるコールバック */
  onClose: () => void
}

// Markdownの<img>をAnt DesignのImageに置き換えてクリック拡大・ズーム・回転を有効化
// 外部リンク（http/https）は別タブで開く
const markdownComponents: Components = {
  img: ({ src, alt }) => {
    if (!src) return null
    return (
      <Image
        src={src}
        alt={alt || ''}
        style={{
          maxWidth: '100%',
          height: 'auto',
          display: 'block',
          margin: '12px 0',
          borderRadius: 6,
          border: `1px solid ${colors.border}`,
          background: colors.bgPrimary,
          cursor: 'zoom-in',
        }}
        preview={{
          mask: <span style={{ fontSize: 13 }}>クリックで拡大</span>,
        }}
      />
    )
  },
  a: ({ href, children, ...props }) => {
    const isExternal = typeof href === 'string' && /^https?:\/\//.test(href)
    return (
      <a
        href={href}
        {...(isExternal ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
        {...props}
      >
        {children}
      </a>
    )
  },
}

export default function HandbookDrawer({ indicatorId, onClose }: HandbookDrawerProps) {
  const navigate = useNavigate()
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [entry, setEntry] = useState<HandbookEntry | null>(null)

  useEffect(() => {
    if (!indicatorId) {
      setContent('')
      setEntry(null)
      return
    }
    const found = HANDBOOK_MAP.get(indicatorId)
    if (!found) {
      setEntry(null)
      setContent('> このコンテンツは準備中です。')
      return
    }
    setEntry(found)
    setLoading(true)
    found
      .loadContent()
      .then((md) => setContent(md))
      .catch(() => setContent('> コンテンツの読み込みに失敗しました。'))
      .finally(() => setLoading(false))
  }, [indicatorId])

  if (!indicatorId) return null

  return (
    <>
      {/* 背景オーバーレイ（クリックで閉じる） */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          top: 64,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.4)',
          zIndex: 199,
        }}
      />
      {/* Drawer本体 - 経済カレンダーの上にオーバーレイ */}
      <div
        style={{
          position: 'fixed',
          right: 0,
          top: 64,
          width: 520,
          maxWidth: '90vw',
          height: 'calc(100vh - 64px)',
          background: colors.bgSecondary,
          borderLeft: `1px solid ${colors.border}`,
          boxShadow: '-8px 0 32px rgba(0, 0, 0, 0.4)',
          zIndex: 200,
          display: 'flex',
          flexDirection: 'column',
          animation: 'slideInRight 0.25s ease-out',
        }}
      >
        {/* ヘッダー */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: `1px solid ${colors.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <Space size={8}>
            <BookOutlined style={{ color: colors.accent, fontSize: 18 }} />
            <Title level={5} style={{ margin: 0, color: colors.textPrimary }}>
              {entry?.title || 'データハンドブック'}
            </Title>
          </Space>
          <Button
            type="text"
            icon={<CloseOutlined style={{ color: colors.textSecondary }} />}
            onClick={onClose}
            size="small"
          />
        </div>

        {/* メタ情報（国・カテゴリ・タグ） */}
        {entry && (
          <div
            style={{
              padding: '12px 20px',
              borderBottom: `1px solid ${colors.border}`,
              flexShrink: 0,
            }}
          >
            <Space size={6} wrap>
              <Tag color="blue">{HANDBOOK_COUNTRY_LABELS[entry.country] || entry.country}</Tag>
              <Tag color="green">{HANDBOOK_CATEGORY_LABELS[entry.category] || entry.category}</Tag>
            </Space>
            <div style={{ marginTop: 8 }}>
              <Text style={{ color: colors.textSecondary, fontSize: 13 }}>{entry.summary}</Text>
            </div>
          </div>
        )}

        {/* コンテンツ */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '20px',
          }}
        >
          {loading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin />
            </div>
          ) : (
            <div className="handbook-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{content}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* フッター - 辞書ページへのリンク */}
        {entry && (
          <div
            style={{
              padding: '12px 20px',
              borderTop: `1px solid ${colors.border}`,
              flexShrink: 0,
            }}
          >
            <Space size={12}>
              <Button
                type="link"
                icon={<LinkOutlined />}
                style={{ color: colors.accent, padding: 0, fontSize: 13 }}
                onClick={() => {
                  onClose()
                  navigate(`/handbook#${entry.indicatorId}`)
                }}
              >
                データハンドブックで詳しく見る
              </Button>
              {entry.relatedIndicators && entry.relatedIndicators.length > 0 && (
                <>
                  <Text style={{ color: colors.textSecondary, fontSize: 12 }}>関連:</Text>
                  {entry.relatedIndicators.slice(0, 3).map((relId) => {
                    const rel = HANDBOOK_MAP.get(relId)
                    return rel ? (
                      <Tag
                        key={relId}
                        style={{
                          cursor: 'pointer',
                          background: colors.bgTertiary,
                          border: `1px solid ${colors.borderLight}`,
                          color: colors.textSecondary,
                          fontSize: 11,
                        }}
                        onClick={() => {
                          // 関連指標を同じDrawerで開く
                          setContent('')
                          setEntry(null)
                          // indicatorIdの変更をトリガー（親から再呼び出しが必要なのでonCloseで代替不可）
                          // → 直接ロード
                          setEntry(rel)
                          setLoading(true)
                          rel
                            .loadContent()
                            .then((md) => setContent(md))
                            .catch(() => setContent('> コンテンツの読み込みに失敗しました。'))
                            .finally(() => setLoading(false))
                        }}
                      >
                        {rel.title}
                      </Tag>
                    ) : null
                  })}
                </>
              )}
            </Space>
          </div>
        )}
      </div>

      {/* Drawer スライドインアニメーション */}
      <style>{`
        @keyframes slideInRight {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }

        .handbook-markdown {
          color: ${colors.textPrimary};
          font-size: 14px;
          line-height: 1.8;
        }
        .handbook-markdown h2 {
          color: ${colors.accent};
          font-size: 17px;
          font-weight: 600;
          margin-top: 24px;
          margin-bottom: 12px;
          padding-bottom: 6px;
          border-bottom: 1px solid ${colors.border};
        }
        .handbook-markdown h3 {
          color: ${colors.textPrimary};
          font-size: 15px;
          font-weight: 600;
          margin-top: 20px;
          margin-bottom: 8px;
        }
        .handbook-markdown p {
          margin-bottom: 12px;
          color: ${colors.textSecondary};
        }
        .handbook-markdown strong {
          color: ${colors.textPrimary};
        }
        .handbook-markdown ul, .handbook-markdown ol {
          padding-left: 20px;
          margin-bottom: 12px;
        }
        .handbook-markdown li {
          color: ${colors.textSecondary};
          margin-bottom: 4px;
        }
        .handbook-markdown table {
          width: 100%;
          border-collapse: collapse;
          margin: 12px 0;
          font-size: 13px;
        }
        .handbook-markdown th {
          background: ${colors.bgTertiary};
          color: ${colors.textPrimary};
          padding: 8px 12px;
          text-align: left;
          border: 1px solid ${colors.borderLight};
          font-weight: 600;
        }
        .handbook-markdown td {
          padding: 6px 12px;
          border: 1px solid ${colors.borderLight};
          color: ${colors.textSecondary};
        }
        .handbook-markdown tr:nth-child(even) td {
          background: rgba(51, 65, 85, 0.3);
        }
        .handbook-markdown blockquote {
          border-left: 3px solid ${colors.accent};
          padding: 8px 16px;
          margin: 12px 0;
          background: rgba(16, 185, 129, 0.05);
          border-radius: 4px;
        }
        .handbook-markdown blockquote p {
          margin: 0;
        }
        .handbook-markdown code {
          background: ${colors.bgTertiary};
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 13px;
          color: ${colors.accentHover};
        }
        .handbook-markdown a {
          color: ${colors.accent};
          text-decoration: none;
        }
        .handbook-markdown a:hover {
          text-decoration: underline;
        }
        .handbook-markdown img {
          max-width: 100%;
          height: auto;
          display: block;
          margin: 12px 0;
          border: 1px solid ${colors.border};
          border-radius: 6px;
          background: ${colors.bgPrimary};
        }
      `}</style>
    </>
  )
}
