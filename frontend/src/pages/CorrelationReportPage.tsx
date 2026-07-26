/**
 * 相関・先行性レポート (master 限定)
 *
 * バックエンドが生成した静的レポート (manifest + sections/*.md + matrices/*.csv) を
 * 表示する。マスター限定は ProtectedRoute(UX) と配信API(require_role) の二重で担保。
 *
 * - GET /api/reports/correlation                 : manifest
 * - GET /api/reports/correlation/section/{id}    : セクション Markdown
 * - GET /api/reports/correlation/download/{name} : CSV (authFetch→blob)
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Layout, Menu, Typography, Button, Tag, Space, Spin, Alert, type MenuProps } from 'antd'
import { DownloadOutlined, BarChartOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { useAuth } from '../contexts/AuthContext'

const { Sider, Content } = Layout
const { Title, Text } = Typography

const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

interface SectionMeta {
  id: string
  title: string
  group: string
}
interface DownloadMeta {
  name: string
  desc: string
}
interface Manifest {
  as_of: string
  generated_at: string
  data_coverage: { start: string; end: string }
  n_series: number
  n_clean: number
  scope: string
  sections: SectionMeta[]
  downloads: DownloadMeta[]
  available_snapshots?: string[]
}

export default function CorrelationReportPage() {
  const { authFetch } = useAuth()
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [selected, setSelected] = useState<string>('overview')
  const [sectionCache, setSectionCache] = useState<Record<string, string>>({})
  const [loadingManifest, setLoadingManifest] = useState(true)
  const [loadingSection, setLoadingSection] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // manifest 取得
  useEffect(() => {
    let alive = true
    ;(async () => {
      setLoadingManifest(true)
      setError(null)
      try {
        const res = await authFetch('/api/reports/correlation')
        if (res.status === 404) {
          throw new Error('レポートが未生成です。バッチ (run.py) を実行してください。')
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = (await res.json()) as Manifest
        if (!alive) return
        setManifest(data)
        if (data.sections?.length) setSelected(data.sections[0].id)
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : '取得に失敗しました')
      } finally {
        if (alive) setLoadingManifest(false)
      }
    })()
    return () => {
      alive = false
    }
  }, [authFetch])

  // セクション Markdown 取得 (キャッシュ)
  useEffect(() => {
    if (!manifest || !selected) return
    if (sectionCache[selected] !== undefined) return
    let alive = true
    ;(async () => {
      setLoadingSection(true)
      try {
        const res = await authFetch(`/api/reports/correlation/section/${selected}`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const text = await res.text()
        if (alive) setSectionCache((p) => ({ ...p, [selected]: text }))
      } catch {
        if (alive) setSectionCache((p) => ({ ...p, [selected]: '## 読み込みに失敗しました' }))
      } finally {
        if (alive) setLoadingSection(false)
      }
    })()
    return () => {
      alive = false
    }
  }, [manifest, selected, sectionCache, authFetch])

  const downloadCsv = useCallback(
    async (name: string) => {
      try {
        const res = await authFetch(`/api/reports/correlation/download/${name}`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = name
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'ダウンロードに失敗しました')
      }
    },
    [authFetch],
  )

  // セクションをグループ化して Menu items に変換
  const menuItems = useMemo<MenuProps['items']>(() => {
    if (!manifest) return []
    const groups = new Map<string, SectionMeta[]>()
    for (const s of manifest.sections) {
      const arr = groups.get(s.group) ?? []
      arr.push(s)
      groups.set(s.group, arr)
    }
    return Array.from(groups.entries()).map(([group, items]) => ({
      key: `grp-${group}`,
      type: 'group' as const,
      label: <span style={{ color: colors.textSecondary }}>{group}</span>,
      children: items.map((s) => ({ key: s.id, label: s.title })),
    }))
  }, [manifest])

  if (loadingManifest) {
    return (
      <div style={{ padding: 48, textAlign: 'center', background: colors.bgPrimary, minHeight: '100vh' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (error && !manifest) {
    return (
      <div style={{ padding: 24, background: colors.bgPrimary, minHeight: '100vh' }}>
        <Alert type="warning" showIcon message="相関レポート" description={error} />
      </div>
    )
  }

  const content = sectionCache[selected] ?? ''

  return (
    <Layout style={{ background: colors.bgPrimary, minHeight: '100vh' }}>
      <Sider width={260} style={{ background: colors.bgSecondary, borderRight: `1px solid ${colors.border}` }}>
        <div style={{ padding: '16px 16px 8px' }}>
          <Space>
            <BarChartOutlined style={{ color: colors.accent, fontSize: 18 }} />
            <Text strong style={{ color: colors.textPrimary }}>
              相関・先行性レポート
            </Text>
          </Space>
          {manifest && (
            <div style={{ marginTop: 8 }}>
              <Tag color="gold">MASTER</Tag>
              <Tag color="default">as-of {manifest.as_of}</Tag>
            </div>
          )}
        </div>
        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[selected]}
          items={menuItems}
          onClick={({ key }) => setSelected(key)}
          style={{ background: colors.bgSecondary, borderInlineEnd: 'none' }}
        />
      </Sider>

      <Content style={{ padding: 24, background: colors.bgPrimary }}>
        {manifest && (
          <div style={{ marginBottom: 16 }}>
            <Title level={4} style={{ color: colors.textPrimary, margin: 0 }}>
              相関・先行性レポート
            </Title>
            <Text style={{ color: colors.textSecondary, fontSize: 12 }}>
              生成 {manifest.generated_at} ／ データ範囲 {manifest.data_coverage.start}〜{manifest.data_coverage.end}{' '}
              ／ 解析対象 {manifest.n_clean.toLocaleString()} 系列 ／ scope={manifest.scope}
            </Text>
          </div>
        )}

        <div className="corr-markdown" style={{ color: colors.textPrimary }}>
          {loadingSection && !content ? (
            <Spin />
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
              {content}
            </ReactMarkdown>
          )}
        </div>

        {manifest && manifest.downloads?.length > 0 && (
          <div
            style={{
              marginTop: 32,
              paddingTop: 16,
              borderTop: `1px solid ${colors.border}`,
            }}
          >
            <Text strong style={{ color: colors.textPrimary }}>
              フル結果ダウンロード（CSV）
            </Text>
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {manifest.downloads.map((d) => (
                <Button
                  key={d.name}
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() => downloadCsv(d.name)}
                  title={d.desc}
                >
                  {d.desc}
                </Button>
              ))}
            </div>
          </div>
        )}
      </Content>

      <style>{`
        .corr-markdown table, .corr-markdown .corr-tbl { border-collapse: collapse; margin: 12px 0; font-size: 12px; }
        .corr-markdown th, .corr-markdown td {
          border: 1px solid ${colors.border}; padding: 4px 8px; text-align: left;
        }
        .corr-markdown th { background: ${colors.bgSecondary}; color: ${colors.accent}; }
        .corr-markdown td { color: ${colors.textPrimary}; }
        .corr-markdown .corr-tbl .rowhdr { background: ${colors.bgSecondary}; font-weight: 600; color: ${colors.accent}; }
        .corr-markdown .corr-tbl.matrix td { white-space: nowrap; }
        .corr-markdown h1 { color: ${colors.textPrimary}; font-size: 22px; margin-top: 8px; }
        .corr-markdown h2 { color: ${colors.accent}; font-size: 18px; margin-top: 24px; }
        .corr-markdown h3 { color: ${colors.textPrimary}; font-size: 15px; margin-top: 16px; }
        .corr-markdown code { background: ${colors.bgSecondary}; padding: 1px 5px; border-radius: 3px; }
        .corr-markdown a { color: ${colors.accent}; }
        .corr-markdown blockquote {
          border-left: 3px solid ${colors.accent}; margin: 12px 0; padding: 4px 12px;
          color: ${colors.textSecondary};
        }
      `}</style>
    </Layout>
  )
}
