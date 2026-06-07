import { useEffect, useMemo, type ReactNode } from 'react'
import { Typography, Space, Image as AntImage } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { useLocation } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { SMC_CONTENT, slugify } from '../content/guides/smc/toc'

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

type Section =
  | { kind: 'h1'; text: string }
  | { kind: 'h2'; text: string; slug: string }
  | { kind: 'h3'; text: string; slug: string }
  | { kind: 'h4'; text: string; slug: string }
  | { kind: 'body'; markdown: string }

function parseSections(md: string): Section[] {
  const lines = md.split('\n')
  const sections: Section[] = []
  let buffer: string[] = []
  let inFence = false
  const slugCounts = new Map<string, number>()

  const allocate = (text: string): string => {
    const base = slugify(text)
    const c = slugCounts.get(base) ?? 0
    slugCounts.set(base, c + 1)
    return c === 0 ? base : `${base}-${c}`
  }

  const flushBody = () => {
    const body = buffer.join('\n').trim()
    if (body) sections.push({ kind: 'body', markdown: body })
    buffer = []
  }

  for (const rawLine of lines) {
    // CRLF 改行のため行末の \r を除去（除去しないと正規表現の `.` と `$` が \r に阻まれて見出しが取れない）
    const line = rawLine.replace(/\r$/, '')
    if (line.startsWith('```')) {
      inFence = !inFence
      buffer.push(line)
      continue
    }
    if (inFence) {
      buffer.push(line)
      continue
    }

    const m1 = /^#\s+(.+)$/.exec(line)
    const m2 = /^##\s+(.+)$/.exec(line)
    const m3 = /^###\s+(.+)$/.exec(line)
    const m4 = /^####\s+(.+)$/.exec(line)

    if (m1) {
      flushBody()
      sections.push({ kind: 'h1', text: m1[1].trim() })
    } else if (m2) {
      flushBody()
      const text = m2[1].trim()
      sections.push({ kind: 'h2', text, slug: allocate(text) })
    } else if (m3) {
      flushBody()
      const text = m3[1].trim()
      sections.push({ kind: 'h3', text, slug: allocate(text) })
    } else if (m4) {
      flushBody()
      const text = m4[1].trim()
      sections.push({ kind: 'h4', text, slug: allocate(text) })
    } else {
      buffer.push(line)
    }
  }
  flushBody()
  return sections
}

export default function SmcHandbookPage() {
  const location = useLocation()
  const sections = useMemo(() => parseSections(SMC_CONTENT), [])

  const markdownComponents = useMemo(
    () => ({
      img: ({ src, alt }: { src?: string; alt?: string }) => {
        if (!src) return null
        return (
          <AntImage
            src={src}
            alt={alt}
            preview={{
              mask: 'クリックで拡大',
            }}
            style={{
              maxWidth: '100%',
              borderRadius: 6,
              border: `1px solid ${colors.border}`,
              cursor: 'zoom-in',
            }}
          />
        )
      },
      // 子に画像を含む段落は <p> ではなく <div> として描画
      // （AntImage が内部で <div> を生成するため p > div の不正なネストを回避）
      p: ({ children, node }: { children?: ReactNode; node?: { children?: Array<{ tagName?: string }> } }) => {
        const hasImg = node?.children?.some((c) => c.tagName === 'img') ?? false
        if (hasImg) {
          return <div style={{ marginBottom: 12 }}>{children}</div>
        }
        return <p>{children}</p>
      },
    }),
    [],
  )

  useEffect(() => {
    if (!location.hash) {
      window.scrollTo({ top: 0 })
      return
    }
    const id = decodeURIComponent(location.hash.replace('#', ''))
    const timer = setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 80)
    return () => clearTimeout(timer)
  }, [location.hash])

  const h1Section = sections.find((s) => s.kind === 'h1') as Extract<Section, { kind: 'h1' }> | undefined
  const intro = (() => {
    const idx = sections.findIndex((s) => s.kind === 'h1')
    if (idx === -1) return null
    const next = sections.slice(idx + 1).find((s) => s.kind !== 'body')
    if (next) {
      const between = sections.slice(idx + 1, sections.indexOf(next))
      return between.find((s) => s.kind === 'body') as Extract<Section, { kind: 'body' }> | undefined
    }
    return sections.slice(idx + 1).find((s) => s.kind === 'body') as Extract<Section, { kind: 'body' }> | undefined
  })()

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
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
            <ThunderboltOutlined />
          </div>
          <div>
            <Title level={2} style={{ margin: 0, color: colors.textPrimary }}>
              {h1Section?.text ?? 'SMC ハンドブック'}
            </Title>
            <Text style={{ color: colors.textSecondary, fontSize: 15 }}>
              Smart Money Concepts のリファレンス
            </Text>
          </div>
        </Space>
      </div>

      {/* 本文 */}
      <div className="smc-markdown">
        {intro && (
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {intro.markdown}
          </ReactMarkdown>
        )}

        {sections.map((s, i) => {
          if (s.kind === 'h1') return null
          if (s.kind === 'body') {
            // intro は既に出力済みなのでスキップ
            if (intro && s === intro) return null
            return (
              <ReactMarkdown key={i} remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {s.markdown}
              </ReactMarkdown>
            )
          }
          if (s.kind === 'h2') {
            return (
              <h2 key={i} id={s.slug} style={{ scrollMarginTop: 80 }}>
                {s.text}
              </h2>
            )
          }
          if (s.kind === 'h3') {
            return (
              <h3 key={i} id={s.slug} style={{ scrollMarginTop: 80 }}>
                {s.text}
              </h3>
            )
          }
          if (s.kind === 'h4') {
            return (
              <h4 key={i} id={s.slug} style={{ scrollMarginTop: 80 }}>
                {s.text}
              </h4>
            )
          }
          return null
        })}
      </div>

      {/* スタイル（DataHandbookPage と同系統） */}
      <style>{`
        .smc-markdown {
          color: ${colors.textPrimary};
          font-size: 14px;
          line-height: 1.8;
        }
        .smc-markdown h2 {
          color: ${colors.accent};
          font-size: 20px;
          font-weight: 600;
          margin-top: 32px;
          margin-bottom: 14px;
          padding-bottom: 8px;
          border-bottom: 1px solid ${colors.border};
        }
        .smc-markdown h3 {
          color: ${colors.textPrimary};
          font-size: 17px;
          font-weight: 600;
          margin-top: 24px;
          margin-bottom: 10px;
        }
        .smc-markdown h4 {
          color: ${colors.textPrimary};
          font-size: 15px;
          font-weight: 600;
          margin-top: 18px;
          margin-bottom: 8px;
        }
        .smc-markdown h5 {
          color: ${colors.textSecondary};
          font-size: 14px;
          font-weight: 600;
          margin-top: 14px;
          margin-bottom: 6px;
        }
        .smc-markdown p {
          margin-bottom: 12px;
          color: ${colors.textSecondary};
        }
        .smc-markdown strong {
          color: ${colors.textPrimary};
        }
        .smc-markdown ul, .smc-markdown ol {
          padding-left: 20px;
          margin-bottom: 12px;
        }
        .smc-markdown li {
          color: ${colors.textSecondary};
          margin-bottom: 4px;
        }
        .smc-markdown table {
          width: 100%;
          border-collapse: collapse;
          margin: 12px 0;
          font-size: 13px;
        }
        .smc-markdown th {
          background: ${colors.bgTertiary};
          color: ${colors.textPrimary};
          padding: 8px 12px;
          text-align: left;
          border: 1px solid ${colors.borderLight};
          font-weight: 600;
        }
        .smc-markdown td {
          padding: 6px 12px;
          border: 1px solid ${colors.borderLight};
          color: ${colors.textSecondary};
        }
        .smc-markdown tr:nth-child(even) td {
          background: rgba(51, 65, 85, 0.3);
        }
        .smc-markdown blockquote {
          border-left: 3px solid ${colors.accent};
          padding: 8px 16px;
          margin: 12px 0;
          background: rgba(16, 185, 129, 0.05);
          border-radius: 4px;
        }
        .smc-markdown blockquote p {
          margin: 0;
          color: ${colors.textSecondary};
        }
        .smc-markdown code {
          background: ${colors.bgTertiary};
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 13px;
          color: ${colors.accentHover};
        }
        .smc-markdown pre {
          background: ${colors.bgTertiary};
          padding: 12px;
          border-radius: 6px;
          overflow-x: auto;
          margin: 12px 0;
        }
        .smc-markdown pre code {
          background: transparent;
          padding: 0;
          color: ${colors.textPrimary};
        }
        .smc-markdown img {
          max-width: 100%;
          height: auto;
          border-radius: 6px;
          margin: 12px 0;
          border: 1px solid ${colors.border};
        }
        .smc-markdown a {
          color: ${colors.accent};
          text-decoration: none;
        }
        .smc-markdown a:hover {
          text-decoration: underline;
        }
        .smc-markdown hr {
          border: none;
          border-top: 1px solid ${colors.border};
          margin: 24px 0;
        }
      `}</style>
    </div>
  )
}
