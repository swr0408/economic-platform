/**
 * 再利用可能なヘッドラインパネル
 * - 各国カテゴリページ：savedOnly表示 → 第2階層/第3階層タグでセクション分け
 * - マーケットページ：全ヘッドライン表示
 */
import { useState, useMemo } from 'react'
import { Typography, Tag, Spin, Empty, Button, Space } from 'antd'
import {
  SoundOutlined, LinkOutlined, ReloadOutlined,
  MinusCircleOutlined, PlusOutlined, CopyOutlined, CheckOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { useHeadlines, useUnsaveHeadline, useCategories, useReorderSavedHeadlines, useReorderSidebarEntries } from '../../hooks/useHeadlines'
import { useIsMaster } from '../../hooks/useIsMaster'
import ManualHeadlineModal from './ManualHeadlineModal'
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
  /** このカテゴリ名（短縮名、例:「雇用」）のセクションを先頭に表示する */
  priorityCategoryName?: string
}

/** 各ヘッドライン行（削除確認ステート付き） */
function HeadlineItem({ item, compact, showCategoryTags = true, sectionCategoryId }: {
  item: Headline; compact: boolean; showCategoryTags?: boolean
  /** グループ表示時の所属カテゴリID（master の行削除＝このカテゴリの保存解除に使う） */
  sectionCategoryId?: number
}) {
  const unsaveMutation = useUnsaveHeadline()
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const isMaster = useIsMaster()

  const text = item.headline_ja || item.headline_raw || ''
  // 長文（120文字超 or 3行以上）は折り畳み表示にする
  const newlineCount = (text.match(/\n/g) || []).length
  const isLong = text.length > 120 || newlineCount >= 2

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        // 非セキュアコンテキスト等のフォールバック
        const ta = document.createElement('textarea')
        ta.value = text
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch {
      /* コピー失敗時は何もしない */
    }
  }

  const publishedTime = item.published_at ? dayjs(item.published_at).format('YYYY/MM/DD HH:mm') : ''
  const hasSaved = item.saved_categories && item.saved_categories.length > 0
  // このセクションに対応する保存レコード（行レベル削除ボタンの対象）
  const sectionSaved = sectionCategoryId != null
    ? item.saved_categories?.find(sc => sc.category_id === sectionCategoryId)
    : undefined

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
      {/* Main text（改行を保持。長文は3行で折り畳み） */}
      <div style={{
        color: colors.textPrimary,
        fontSize: compact ? 11 : 12,
        lineHeight: 1.5,
        wordBreak: 'break-word',
        whiteSpace: 'pre-wrap',
        ...(isLong && !expanded ? {
          display: '-webkit-box',
          WebkitLineClamp: 3,
          WebkitBoxOrient: 'vertical' as const,
          overflow: 'hidden',
        } : {}),
      }}>
        {text}
      </div>
      {isLong && (
        <span
          onClick={(e) => { e.stopPropagation(); setExpanded(v => !v) }}
          style={{
            color: colors.accent,
            fontSize: compact ? 10 : 11,
            cursor: 'pointer',
            display: 'inline-block',
            marginTop: 2,
            userSelect: 'none',
          }}
        >
          {expanded ? '折りたたむ ▲' : '続きを表示 ▼'}
        </span>
      )}

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
        {copied
          ? <CheckOutlined style={{ fontSize: 11, color: colors.accent }} title="コピーしました" />
          : <CopyOutlined
              onClick={handleCopy}
              style={{ fontSize: 11, color: colors.textTertiary, cursor: 'pointer', transition: 'color 0.15s' }}
              onMouseEnter={e => (e.currentTarget.style.color = colors.textPrimary)}
              onMouseLeave={e => (e.currentTarget.style.color = colors.textTertiary)}
              title="本文をコピー"
            />
        }
        {showCategoryTags && hasSaved && item.saved_categories!.map(sc => (
          <span key={sc.saved_id} style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
            <Tag
              color={sc.category_color}
              style={{ margin: 0, fontSize: 9, lineHeight: '16px', padding: '0 3px' }}
            >
              {sc.category_name}
            </Tag>
            {isMaster && (
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
            )}
          </span>
        ))}
        {/* グループ表示時の行削除（master 限定: このセクションのカテゴリから保存解除） */}
        {isMaster && sectionSaved && (
          <MinusCircleOutlined
            onClick={(e) => { e.stopPropagation(); handleDelete(sectionSaved.saved_id) }}
            style={{
              fontSize: 10,
              color: confirmDeleteId === sectionSaved.saved_id ? '#ef4444' : colors.textTertiary,
              cursor: 'pointer',
              transition: 'color 0.15s',
              marginLeft: 'auto',
            }}
            title={confirmDeleteId === sectionSaved.saved_id ? 'もう一度クリックで削除' : 'この一覧から削除（保存解除）'}
          />
        )}
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
interface ChildSection {
  childCategory: { id: number; name: string; color: string; sort_order: number | null }
  items: Headline[]
}

interface CategorySection {
  /** 第2層カテゴリ */
  parentCategory: { id: number; name: string; color: string }
  /** 第2層に直接保存されたヘッドライン */
  directItems: Headline[]
  /** 第3層サブセクション */
  childSections: ChildSection[]
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
        childCategory: {
          id: cs.childCat.id, name: cs.childCat.name, color: cs.childCat.color,
          sort_order: cs.childCat.sort_order ?? null,
        },
        items: cs.items,
      })),
    })
  }

  return sections
}

/** セクション内の表示順: 手動並び替え済み (sort_order 昇順) より前に、
 *  未並び替えの新着 (sort_order=null) を元の順序 (published_at 降順) のまま置く */
function sortBySavedOrder(items: Headline[], categoryId: number): Headline[] {
  const so = (h: Headline) =>
    h.saved_categories?.find(sc => sc.category_id === categoryId)?.sort_order ?? null
  return [...items].sort((a, b) => {
    const sa = so(a), sb = so(b)
    if (sa === null && sb === null) return 0
    if (sa === null) return -1
    if (sb === null) return 1
    return sa - sb
  })
}

/** セクション内ヘッドラインリスト（master はドラッグ&ドロップで並び替え可能） */
function SortableSectionItems({ items, categoryId, compact }: {
  items: Headline[]; categoryId: number; compact: boolean
}) {
  const isMaster = useIsMaster()
  const reorderMutation = useReorderSavedHeadlines()
  const [dragIdx, setDragIdx] = useState<number | null>(null)
  const [overIdx, setOverIdx] = useState<number | null>(null)

  const sorted = useMemo(() => sortBySavedOrder(items, categoryId), [items, categoryId])

  const handleDrop = (toIdx: number) => {
    if (dragIdx === null || dragIdx === toIdx) {
      setDragIdx(null); setOverIdx(null)
      return
    }
    const next = [...sorted]
    const [moved] = next.splice(dragIdx, 1)
    next.splice(toIdx, 0, moved)
    const savedIds = next
      .map(h => h.saved_categories?.find(sc => sc.category_id === categoryId)?.saved_id)
      .filter((v): v is number => v != null)
    reorderMutation.mutate({ categoryId, savedIds })
    setDragIdx(null); setOverIdx(null)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      {sorted.map((item, idx) => (
        <div
          key={item.id}
          draggable={isMaster}
          // 親 (SectionBody) のD&Dとネストするため、ドラッグ開始は伝播を止め、
          // over/drop は自リスト内ドラッグ中のみ処理する (それ以外は親へバブル)
          onDragStart={isMaster ? (e) => {
            e.stopPropagation()
            e.dataTransfer.setData('text/plain', '')
            e.dataTransfer.effectAllowed = 'move'
            setDragIdx(idx)
          } : undefined}
          onDragOver={isMaster ? (e) => {
            if (dragIdx !== null) { e.preventDefault(); e.stopPropagation(); setOverIdx(idx) }
          } : undefined}
          onDrop={isMaster ? (e) => {
            if (dragIdx !== null) { e.preventDefault(); e.stopPropagation(); handleDrop(idx) }
          } : undefined}
          onDragEnd={isMaster ? (e) => { e.stopPropagation(); setDragIdx(null); setOverIdx(null) } : undefined}
          style={{
            opacity: dragIdx === idx ? 0.4 : 1,
            borderTop: overIdx === idx && dragIdx !== null && dragIdx !== idx
              ? `2px solid ${colors.accent}`
              : '2px solid transparent',
            cursor: isMaster ? 'grab' : 'default',
          }}
        >
          <HeadlineItem item={item} compact={compact} showCategoryTags={false} sectionCategoryId={categoryId} />
        </div>
      ))}
    </div>
  )
}

/** セクション内の並び替え対象エントリ（直下ヘッドライン or 子カテゴリブロック） */
type SectionEntry =
  | { kind: 'item'; key: string; item: Headline; savedId: number; order: number | null }
  | { kind: 'child'; key: string; cs: ChildSection; order: number | null }

/** 直下ヘッドラインと子カテゴリブロックを統一順序に並べる
 *  (order=null は未並び替え → 従来表示順のまま先頭グループに) */
function buildSectionEntries(section: CategorySection): SectionEntry[] {
  const entries: SectionEntry[] = []
  for (const item of section.directItems) {
    const sc = item.saved_categories?.find(s => s.category_id === section.parentCategory.id)
    if (!sc) continue
    entries.push({ kind: 'item', key: `i${item.id}`, item, savedId: sc.saved_id, order: sc.sort_order ?? null })
  }
  for (const cs of section.childSections) {
    entries.push({ kind: 'child', key: `c${cs.childCategory.id}`, cs, order: cs.childCategory.sort_order })
  }
  return entries.sort((a, b) => {
    if (a.order === null && b.order === null) return 0
    if (a.order === null) return -1
    if (b.order === null) return 1
    return a.order - b.order
  })
}

/** 第2層セクション本体: 直下ヘッドラインと子カテゴリブロックを
 *  master はドラッグ&ドロップで自由に並び替えできる */
function SectionBody({ section, compact }: { section: CategorySection; compact: boolean }) {
  const isMaster = useIsMaster()
  const reorderMutation = useReorderSidebarEntries()
  const [dragIdx, setDragIdx] = useState<number | null>(null)
  const [overIdx, setOverIdx] = useState<number | null>(null)

  const entries = useMemo(() => buildSectionEntries(section), [section])

  const resetDrag = () => { setDragIdx(null); setOverIdx(null) }

  const handleDrop = (toIdx: number) => {
    if (dragIdx === null || dragIdx === toIdx) { resetDrag(); return }
    const next = [...entries]
    const [moved] = next.splice(dragIdx, 1)
    next.splice(toIdx, 0, moved)
    const payload = next.map((en, idx) =>
      en.kind === 'item'
        ? { type: 'saved' as const, id: en.savedId, sortOrder: idx }
        : { type: 'category' as const, id: en.cs.childCategory.id, sortOrder: idx }
    )
    reorderMutation.mutate({ entries: payload })
    resetDrag()
  }

  const handleDragStart = (idx: number) => (e: React.DragEvent) => {
    e.dataTransfer.setData('text/plain', '')
    e.dataTransfer.effectAllowed = 'move'
    setDragIdx(idx)
  }

  // ドロップ受け側 (セクションレベルのドラッグ中のみ反応し、子リストのD&Dには干渉しない)
  const dropTargetProps = (idx: number) => isMaster ? {
    onDragOver: (e: React.DragEvent) => {
      if (dragIdx !== null) { e.preventDefault(); setOverIdx(idx) }
    },
    onDrop: (e: React.DragEvent) => {
      if (dragIdx !== null) { e.preventDefault(); handleDrop(idx) }
    },
  } : {}

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {entries.map((en, idx) => {
        const highlight = overIdx === idx && dragIdx !== null && dragIdx !== idx
        const borderTop = highlight ? `2px solid ${colors.accent}` : '2px solid transparent'

        if (en.kind === 'item') {
          return (
            <div
              key={en.key}
              draggable={isMaster}
              onDragStart={isMaster ? handleDragStart(idx) : undefined}
              onDragEnd={isMaster ? resetDrag : undefined}
              {...dropTargetProps(idx)}
              style={{
                opacity: dragIdx === idx ? 0.4 : 1,
                borderTop,
                cursor: isMaster ? 'grab' : 'default',
              }}
            >
              <HeadlineItem
                item={en.item} compact={compact} showCategoryTags={false}
                sectionCategoryId={section.parentCategory.id}
              />
            </div>
          )
        }

        const cs = en.cs
        return (
          <div
            key={en.key}
            {...dropTargetProps(idx)}
            style={{
              marginTop: idx === 0 ? 0 : 6,
              opacity: dragIdx === idx ? 0.4 : 1,
              borderTop,
            }}
          >
            {/* 第3層サブヘッダー (ここを掴んでブロックごと並び替え) */}
            <div
              draggable={isMaster}
              onDragStart={isMaster ? handleDragStart(idx) : undefined}
              onDragEnd={isMaster ? resetDrag : undefined}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                marginLeft: 8,
                marginBottom: 4,
                cursor: isMaster ? 'grab' : 'default',
              }}
            >
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

            <div style={{ marginLeft: 8 }}>
              <SortableSectionItems
                items={cs.items}
                categoryId={cs.childCategory.id}
                compact={compact}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
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
  priorityCategoryName,
}: HeadlinePanelProps) {
  const queryParams: HeadlinesParams = {
    limit,
    ...externalParams,
  }

  const { data, isLoading, refetch, isFetching } = useHeadlines(queryParams)
  const { data: allCategories = [] } = useCategories()
  const isMaster = useIsMaster()
  const [manualOpen, setManualOpen] = useState(false)

  const isSavedMode = !!externalParams?.savedOnly
  const countryPrefix = externalParams?.savedCategoryPrefix

  const sections = useMemo(() => {
    if (!isSavedMode || !data?.items) return []
    const built = buildCategorySections(data.items, allCategories, countryPrefix)
    // 現在ページのカテゴリ（例: 雇用ページなら「雇用」）のセクションを先頭へ
    if (priorityCategoryName) {
      built.sort((a, b) => {
        const ap = shortCatName(a.parentCategory.name) === priorityCategoryName ? 0 : 1
        const bp = shortCatName(b.parentCategory.name) === priorityCategoryName ? 0 : 1
        return ap - bp
      })
    }
    return built
  }, [data?.items, allCategories, isSavedMode, countryPrefix, priorityCategoryName])

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
        <Space size={2}>
          {isMaster && (
            <Button
              type="text"
              size="small"
              icon={<PlusOutlined />}
              onClick={() => setManualOpen(true)}
              style={{ color: colors.accent, padding: '0 4px' }}
              title="ヘッドラインを手動登録"
            />
          )}
          <Button
            type="text"
            size="small"
            icon={<ReloadOutlined spin={isFetching} />}
            onClick={() => refetch()}
            style={{ color: colors.textSecondary, padding: '0 4px' }}
          />
        </Space>
      </div>

      {/* Manual headline registration (master only) */}
      {manualOpen && isMaster && (
        <ManualHeadlineModal
          onClose={() => setManualOpen(false)}
          defaultCategoryPrefix={countryPrefix}
        />
      )}

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

              {/* 直下ヘッドライン + 第3層サブセクション (master はD&Dで並び替え可能) */}
              <SectionBody section={section} compact={compact} />
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
