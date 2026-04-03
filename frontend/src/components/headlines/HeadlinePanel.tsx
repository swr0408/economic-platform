/**
 * 再利用可能なヘッドラインパネル
 * - 各国カテゴリページ：savedOnly表示 → 第2階層/第3階層タグでセクション分け
 * - マーケットページ：全ヘッドライン表示
 */
import { useState, useMemo } from 'react'
import { Typography, Tag, Spin, Empty, Button, Space } from 'antd'
import {
  SoundOutlined, LinkOutlined, ReloadOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { useHeadlines, useUnsaveHeadline, useCategories } from '../../hooks/useHeadlines'
import type { HeadlinesParams, Headline, Category } from '../../api/headlinesApi'

const { Text } = Typography

const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
}

const CATEGORY_COLORS: Record<string, string> = {
  central_bank: '#f59e0b',
  macro: '#3b82f6',
  oil_energy: '#ef4444',
  geopolitics: '#a855f7',
  equities: '#10b981',
  rates_fx: '#06b6d4',
  other: '#64748b',
}

const CATEGORY_LABELS: Record<string, string> = {
  central_bank: '中銀',
  macro: 'マクロ',
  oil_energy: '原油',
  geopolitics: '地政学',
  equities: '株式',
  rates_fx: '金利/FX',
  other: 'その他',
}

interface HeadlinePanelProps {
  /** ヘッドライン取得パラメータ */
  params?: HeadlinesParams
  /** パネルタイトル */
  title?: string
  /** 表示件数 */
  limit?: number
  /** コンパクトモード */
  compact?: boolean
}

/** 各ヘッドライン行（削除確認ステート付き） */
function HeadlineItem({ item, compact, showCategoryTags = true }: {
  item: Headline; compact: boolean; showCategoryTags?: boolean
}) {
  const unsaveMutation = useUnsaveHeadline()
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)

  const publishedTime = item.published_at ? dayjs(item.published_at).format('YYYY/MM/DD HH:mm') : ''
  const hasSaved = item.saved_categories && item.saved_categories.length > 0

  const handleDelete = (savedId: number) => {
    if (confirmDeleteId === savedId) {
      unsaveMutation.mutate({ headlineId: item.id, savedId })
      setConfirmDeleteId(null)
    } else {
      setConfirmDeleteId(savedId)
    }
  }

  return (
    <div
      style={{
        padding: compact ? '6px 8px' : '8px 10px',
        borderRadius: 4,
        transition: 'background-color 0.15s',
        cursor: 'default',
      }}
      onMouseEnter={e => (e.currentTarget.style.backgroundColor = colors.bgTertiary)}
      onMouseLeave={e => {
        e.currentTarget.style.backgroundColor = 'transparent'
        setConfirmDeleteId(null)
      }}
    >
      {/* Main text */}
      <div style={{
        color: colors.textPrimary,
        fontSize: compact ? 11 : 12,
        lineHeight: 1.5,
        wordBreak: 'break-word',
      }}>
        {item.headline_ja || item.headline_raw}
      </div>

      {/* Meta row */}
      <div style={{
        display: 'flex', gap: 6, alignItems: 'center', marginTop: 3,
        flexWrap: 'wrap',
      }}>
        <Text style={{ color: colors.textTertiary, fontSize: 10 }}>{publishedTime}</Text>
        {item.rough_category && (
          <Tag
            color={CATEGORY_COLORS[item.rough_category]}
            style={{ margin: 0, fontSize: 9, lineHeight: '16px', padding: '0 3px', borderColor: 'transparent' }}
          >
            {CATEGORY_LABELS[item.rough_category] || item.rough_category}
          </Tag>
        )}
        {item.speaker_name && (
          <Text style={{ color: colors.accent, fontSize: 10 }}>{item.speaker_name}</Text>
        )}
        {item.external_link && (
          <a href={item.external_link} target="_blank" rel="noopener noreferrer"
            style={{ color: colors.textTertiary, fontSize: 10 }}>
            <LinkOutlined />
          </a>
        )}
        {showCategoryTags && hasSaved && item.saved_categories!.map(sc => (
          <span key={sc.saved_id} style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
            <Tag
              color={sc.category_color}
              style={{ margin: 0, fontSize: 9, lineHeight: '16px', padding: '0 3px' }}
            >
              {sc.category_name}
            </Tag>
            <MinusCircleOutlined
              onClick={(e) => { e.stopPropagation(); handleDelete(sc.saved_id) }}
              style={{
                fontSize: 10,
                color: confirmDeleteId === sc.saved_id ? '#ef4444' : colors.textTertiary,
                cursor: 'pointer',
                transition: 'color 0.15s',
              }}
              title={confirmDeleteId === sc.saved_id ? 'もう一度クリックで削除' : '保存を解除'}
            />
          </span>
        ))}
      </div>

      {confirmDeleteId !== null && (
        <div style={{
          marginTop: 4, fontSize: 10, color: '#ef4444',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <span>もう一度 - をクリックで削除</span>
          <span
            onClick={() => setConfirmDeleteId(null)}
            style={{ color: colors.textTertiary, cursor: 'pointer', textDecoration: 'underline' }}
          >
            キャンセル
          </span>
        </div>
      )}
    </div>
  )
}

/** カテゴリ階層でグループ化されたセクション */
interface CategorySection {
  /** 第2層カテゴリ */
  parentCategory: { id: number; name: string; color: string }
  /** 第2層に直接保存されたヘッドライン */
  directItems: Headline[]
  /** 第3層サブセクション */
  childSections: {
    childCategory: { id: number; name: string; color: string }
    items: Headline[]
  }[]
}

/** ヘッドラインをカテゴリ階層でグループ化 */
function buildCategorySections(
  items: Headline[],
  allCategories: Category[],
  countryPrefix?: string,
): CategorySection[] {
  // カテゴリマスタからparent_idマップを構築
  const catMap = new Map<number, Category>()
  for (const c of allCategories) catMap.set(c.id, c)

  // 第2層カテゴリ → { directItems, childMap: { childCatId → items } }
  const sectionMap = new Map<number, {
    parentCat: Category
    directItems: Headline[]
    childMap: Map<number, { childCat: Category; items: Headline[] }>
  }>()

  const seenHeadlineIds = new Set<number>()

  for (const item of items) {
    if (!item.saved_categories || item.saved_categories.length === 0) continue

    for (const sc of item.saved_categories) {
      const cat = catMap.get(sc.category_id)
      if (!cat) continue

      // 国プレフィックスフィルタ（「日本:」配下のみ表示）
      if (countryPrefix) {
        const isRelevant = cat.parent_id === null
          ? cat.name.startsWith(countryPrefix)
          : (() => {
              const parent = catMap.get(cat.parent_id!)
              return parent ? parent.name.startsWith(countryPrefix) : false
            })()
        if (!isRelevant) continue
      }

      if (cat.parent_id === null) {
        // 第2層カテゴリに直接保存
        if (!sectionMap.has(cat.id)) {
          sectionMap.set(cat.id, { parentCat: cat, directItems: [], childMap: new Map() })
        }
        const section = sectionMap.get(cat.id)!
        if (!section.directItems.some(h => h.id === item.id)) {
          section.directItems.push(item)
        }
      } else {
        // 第3層カテゴリ → 親の第2層セクションに追加
        const parentCat = catMap.get(cat.parent_id!)
        if (!parentCat) continue
        const parentId = parentCat.id

        if (!sectionMap.has(parentId)) {
          sectionMap.set(parentId, { parentCat: parentCat, directItems: [], childMap: new Map() })
        }
        const section = sectionMap.get(parentId)!
        if (!section.childMap.has(cat.id)) {
          section.childMap.set(cat.id, { childCat: cat, items: [] })
        }
        const childSection = section.childMap.get(cat.id)!
        if (!childSection.items.some(h => h.id === item.id)) {
          childSection.items.push(item)
        }
      }
      seenHeadlineIds.add(item.id)
    }
  }

  // Map → 配列に変換
  const sections: CategorySection[] = []
  for (const [, val] of sectionMap) {
    sections.push({
      parentCategory: { id: val.parentCat.id, name: val.parentCat.name, color: val.parentCat.color },
      directItems: val.directItems,
      childSections: Array.from(val.childMap.values()).map(cs => ({
        childCategory: { id: cs.childCat.id, name: cs.childCat.name, color: cs.childCat.color },
        items: cs.items,
      })),
    })
  }

  return sections
}

/** カテゴリ名から短縮名を取得（「日本: 金融政策」→「金融政策」） */
function shortCatName(name: string): string {
  const idx = name.indexOf(':')
  return idx > 0 ? name.substring(idx + 1).trim() : name
}

function HeadlinePanel({
  params: externalParams,
  title = 'ヘッドライン',
  limit = 20,
  compact = false,
}: HeadlinePanelProps) {
  const queryParams: HeadlinesParams = {
    limit,
    ...externalParams,
  }

  const { data, isLoading, refetch, isFetching } = useHeadlines(queryParams)
  const { data: allCategories = [] } = useCategories()

  const isSavedMode = !!externalParams?.savedOnly
  const countryPrefix = externalParams?.savedCategoryPrefix

  const sections = useMemo(() => {
    if (!isSavedMode || !data?.items) return []
    return buildCategorySections(data.items, allCategories, countryPrefix)
  }, [data?.items, allCategories, isSavedMode, countryPrefix])

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: compact ? 20 : 40 }}>
        <Spin size="small" />
      </div>
    )
  }

  const items = data?.items || []

  return (
    <div>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 8,
        paddingBottom: 8,
        borderBottom: `1px solid ${colors.border}`,
      }}>
        <Space size={6}>
          <SoundOutlined style={{ fontSize: 14, color: colors.accent }} />
          <Text strong style={{ fontSize: 13, color: colors.textPrimary }}>{title}</Text>
          {data && (
            <Text style={{ color: colors.textTertiary, fontSize: 11 }}>{data.total}件</Text>
          )}
        </Space>
        <Button
          type="text"
          size="small"
          icon={<ReloadOutlined spin={isFetching} />}
          onClick={() => refetch()}
          style={{ color: colors.textSecondary, padding: '0 4px' }}
        />
      </div>

      {/* List */}
      {items.length === 0 ? (
        <Empty description="ヘッドラインなし" image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ padding: compact ? 12 : 24 }} />
      ) : isSavedMode && sections.length > 0 ? (
        /* カテゴリ階層でグループ表示 */
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {sections.map(section => (
            <div key={section.parentCategory.id}>
              {/* 第2層セクションヘッダー */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                marginBottom: 6,
                paddingBottom: 4,
                borderBottom: `2px solid ${section.parentCategory.color}40`,
              }}>
                <div style={{
                  width: 3, height: 14, borderRadius: 2,
                  background: section.parentCategory.color,
                }} />
                <Text strong style={{
                  fontSize: 12, color: colors.textPrimary,
                }}>
                  {shortCatName(section.parentCategory.name)}
                </Text>
                <Text style={{ color: colors.textTertiary, fontSize: 10 }}>
                  {section.directItems.length + section.childSections.reduce((s, cs) => s + cs.items.length, 0)}件
                </Text>
              </div>

              {/* 第2層に直接保存されたヘッドライン */}
              {section.directItems.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {section.directItems.map(item => (
                    <HeadlineItem key={item.id} item={item} compact={compact} showCategoryTags={false} />
                  ))}
                </div>
              )}

              {/* 第3層サブセクション */}
              {section.childSections.map(cs => (
                <div key={cs.childCategory.id} style={{ marginTop: section.directItems.length > 0 ? 8 : 0 }}>
                  {/* 第3層サブヘッダー */}
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    marginLeft: 8,
                    marginBottom: 4,
                  }}>
                    <Tag
                      color={cs.childCategory.color}
                      style={{
                        margin: 0, fontSize: 10, lineHeight: '18px',
                        padding: '0 5px', borderColor: 'transparent',
                      }}
                    >
                      {cs.childCategory.name}
                    </Tag>
                    <Text style={{ color: colors.textTertiary, fontSize: 10 }}>
                      {cs.items.length}件
                    </Text>
                  </div>

                  <div style={{ marginLeft: 8, display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {cs.items.map(item => (
                      <HeadlineItem key={item.id} item={item} compact={compact} showCategoryTags={false} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        /* フラットリスト（非saved モード） */
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {items.map(item => (
            <HeadlineItem key={item.id} item={item} compact={compact} />
          ))}
        </div>
      )}
    </div>
  )
}

export default HeadlinePanel
