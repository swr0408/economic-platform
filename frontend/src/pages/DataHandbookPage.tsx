import { useState, useEffect, useMemo } from 'react'
import { Typography, Input, Tag, Space, Card, Spin, Empty } from 'antd'
import { SearchOutlined, BookOutlined } from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  HANDBOOK_ENTRIES,
  HANDBOOK_MAP,
  HANDBOOK_COUNTRY_LABELS,
  HANDBOOK_CATEGORY_LABELS,
  sortHandbookEntries,
  type HandbookEntry,
} from '../content/handbookRegistry'

const { Title, Text } = Typography

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

// カテゴリの色
const CATEGORY_COLORS: Record<string, string> = {
  policy: '#1890ff',
  economy: '#52c41a',
  consumer: '#13c2c2',
  employment: '#faad14',
  inflation: '#ff4d4f',
  housing: '#722ed1',
}

function HandbookArticle({ entry }: { entry: HandbookEntry }) {
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    entry
      .loadContent()
      .then((md) => setContent(md))
      .catch(() => setContent('> コンテンツの読み込みに失敗しました。'))
      .finally(() => setLoading(false))
  }, [entry])

  return (
    <Card
      id={entry.indicatorId}
      style={{
        marginBottom: 24,
        background: colors.bgSecondary,
        border: `1px solid ${colors.borderLight}`,
        borderRadius: 12,
        scrollMarginTop: 80,
      }}
    >
      {/* ヘッダー */}
      <div style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
          {entry.title}
        </Title>
        <Space size={6} style={{ marginTop: 8 }} wrap>
          <Tag color="blue">{HANDBOOK_COUNTRY_LABELS[entry.country]}</Tag>
          <Tag
            style={{
              background: `${CATEGORY_COLORS[entry.category]}20`,
              borderColor: CATEGORY_COLORS[entry.category],
              color: CATEGORY_COLORS[entry.category],
            }}
          >
            {HANDBOOK_CATEGORY_LABELS[entry.category]}
          </Tag>
          {entry.tags?.map((tag) => (
            <Tag
              key={tag}
              style={{
                background: colors.bgTertiary,
                border: `1px solid ${colors.borderLight}`,
                color: colors.textSecondary,
                fontSize: 11,
              }}
            >
              {tag}
            </Tag>
          ))}
        </Space>
        <div style={{ marginTop: 8 }}>
          <Text style={{ color: colors.textSecondary, fontSize: 14 }}>{entry.summary}</Text>
        </div>
      </div>

      {/* コンテンツ */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin />
        </div>
      ) : (
        <div className="handbook-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      )}

      {/* 関連指標 */}
      {entry.relatedIndicators && entry.relatedIndicators.length > 0 && (
        <div
          style={{
            marginTop: 20,
            paddingTop: 16,
            borderTop: `1px solid ${colors.border}`,
          }}
        >
          <Text style={{ color: colors.textSecondary, fontSize: 13 }}>関連指標: </Text>
          <Space size={6} wrap style={{ marginTop: 4 }}>
            {entry.relatedIndicators.map((relId) => {
              const rel = HANDBOOK_MAP.get(relId)
              return rel ? (
                <Tag
                  key={relId}
                  style={{
                    cursor: 'pointer',
                    background: `${colors.accent}15`,
                    border: `1px solid ${colors.accent}40`,
                    color: colors.accent,
                    fontSize: 12,
                  }}
                  onClick={() => {
                    navigate(`/handbook#${relId}`)
                    setTimeout(() => {
                      document.getElementById(relId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                    }, 100)
                  }}
                >
                  {rel.title}
                </Tag>
              ) : null
            })}
          </Space>
        </div>
      )}
    </Card>
  )
}

export default function DataHandbookPage() {
  const location = useLocation()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)

  // ハッシュがある場合はスクロール
  useEffect(() => {
    if (location.hash) {
      const id = location.hash.replace('#', '')
      setTimeout(() => {
        document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 200)
    }
  }, [location.hash])

  // サイドバーと一致する順序でソートされた全エントリー
  const sortedEntries = useMemo(() => sortHandbookEntries(HANDBOOK_ENTRIES), [])

  // フィルタリング
  const filteredEntries = useMemo(() => {
    return sortedEntries.filter((entry) => {
      // 国フィルタ
      if (selectedCountry && entry.country !== selectedCountry) return false
      // カテゴリフィルタ
      if (selectedCategory && entry.category !== selectedCategory) return false
      // テキスト検索
      if (searchQuery) {
        const q = searchQuery.toLowerCase()
        return (
          entry.title.toLowerCase().includes(q) ||
          entry.summary.toLowerCase().includes(q) ||
          (entry.tags || []).some((t) => t.toLowerCase().includes(q))
        )
      }
      return true
    })
  }, [sortedEntries, searchQuery, selectedCountry, selectedCategory])

  // 利用可能な国・カテゴリ一覧（ソート済みエントリー順を反映）
  const availableCountries = useMemo(
    () => [...new Set(sortedEntries.map((e) => e.country))],
    [sortedEntries]
  )
  const availableCategories = useMemo(
    () => [...new Set(sortedEntries.map((e) => e.category))],
    [sortedEntries]
  )

  return (
    <div style={{ padding: '24px', maxWidth: 900 }}>
      {/* ヘッダー */}
      <div style={{ marginBottom: 32 }}>
        <Space size={16} align="center">
          <div
            style={{
              color: colors.accent,
              fontSize: 32,
              background: `${colors.accent}15`,
              width: 56,
              height: 56,
              borderRadius: 12,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <BookOutlined />
          </div>
          <div>
            <Title level={2} style={{ margin: 0, color: colors.textPrimary }}>
              データハンドブック
            </Title>
            <Text style={{ color: colors.textSecondary, fontSize: 15 }}>
              経済指標の解説・発表スケジュール・トレードの着眼点
            </Text>
          </div>
        </Space>
      </div>

      {/* 検索 & フィルタ */}
      <div style={{ marginBottom: 24 }}>
        <Input
          placeholder="指標名・キーワードで検索..."
          prefix={<SearchOutlined style={{ color: colors.textSecondary }} />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          allowClear
          size="large"
          style={{
            background: colors.bgSecondary,
            borderColor: colors.borderLight,
            color: colors.textPrimary,
            marginBottom: 12,
          }}
        />

        {/* 国フィルタ */}
        <div style={{ marginBottom: 8 }}>
          <Text style={{ color: colors.textSecondary, fontSize: 12, marginRight: 8 }}>国:</Text>
          <Tag
            style={{
              cursor: 'pointer',
              background: !selectedCountry ? colors.accent : colors.bgTertiary,
              borderColor: !selectedCountry ? colors.accent : colors.borderLight,
              color: !selectedCountry ? '#fff' : colors.textSecondary,
            }}
            onClick={() => setSelectedCountry(null)}
          >
            すべて
          </Tag>
          {availableCountries.map((code) => (
            <Tag
              key={code}
              style={{
                cursor: 'pointer',
                background: selectedCountry === code ? colors.accent : colors.bgTertiary,
                borderColor: selectedCountry === code ? colors.accent : colors.borderLight,
                color: selectedCountry === code ? '#fff' : colors.textSecondary,
              }}
              onClick={() => setSelectedCountry(selectedCountry === code ? null : code)}
            >
              {HANDBOOK_COUNTRY_LABELS[code]}
            </Tag>
          ))}
        </div>

        {/* カテゴリフィルタ */}
        <div>
          <Text style={{ color: colors.textSecondary, fontSize: 12, marginRight: 8 }}>カテゴリ:</Text>
          <Tag
            style={{
              cursor: 'pointer',
              background: !selectedCategory ? colors.accent : colors.bgTertiary,
              borderColor: !selectedCategory ? colors.accent : colors.borderLight,
              color: !selectedCategory ? '#fff' : colors.textSecondary,
            }}
            onClick={() => setSelectedCategory(null)}
          >
            すべて
          </Tag>
          {availableCategories.map((code) => (
            <Tag
              key={code}
              style={{
                cursor: 'pointer',
                background: selectedCategory === code ? (CATEGORY_COLORS[code] || colors.accent) : colors.bgTertiary,
                borderColor: selectedCategory === code ? (CATEGORY_COLORS[code] || colors.accent) : colors.borderLight,
                color: selectedCategory === code ? '#fff' : colors.textSecondary,
              }}
              onClick={() => setSelectedCategory(selectedCategory === code ? null : code)}
            >
              {HANDBOOK_CATEGORY_LABELS[code]}
            </Tag>
          ))}
        </div>
      </div>

      {/* 件数 */}
      <div style={{ marginBottom: 16 }}>
        <Text style={{ color: colors.textSecondary, fontSize: 13 }}>
          {filteredEntries.length} 件の指標
        </Text>
      </div>

      {/* 記事一覧 */}
      {filteredEntries.length > 0 ? (
        filteredEntries.map((entry) => (
          <HandbookArticle key={entry.indicatorId} entry={entry} />
        ))
      ) : (
        <Empty
          description={
            <Text style={{ color: colors.textSecondary }}>
              該当する指標が見つかりませんでした
            </Text>
          }
          style={{ padding: 60 }}
        />
      )}

      {/* Markdown スタイル（Drawerと同じ） */}
      <style>{`
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
      `}</style>
    </div>
  )
}
