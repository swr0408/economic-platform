/**
 * カテゴリ選択ツリー（国グループ → 第2層 → 第3層）
 * SaveToCategoryModal / ManualHeadlineModal で共有。
 * 選択状態 (selectedIds) と新規トップレベル名 (newCategoryName) は呼び出し側が保持する。
 */
import { useEffect, useMemo, useState } from 'react'
import { Input, Tag, Typography, Spin, message } from 'antd'
import { PlusOutlined, RightOutlined, DownOutlined } from '@ant-design/icons'
import { useCategories, useCreateCategory } from '../../hooks/useHeadlines'
import type { Category } from '../../api/headlinesApi'

const { Text } = Typography

const colors = {
  bgTertiary: '#334155',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
  accent: '#10b981',
}

/** 国グループ → カテゴリ → 子カテゴリ のツリー構造 */
interface CategoryGroup {
  groupName: string
  /** 第2層: parent_id = null のカテゴリ */
  categories: (Category & { children: Category[] })[]
}

function buildCategoryTree(categories: Category[]): CategoryGroup[] {
  const roots = categories.filter(c => c.parent_id === null)
  const childMap = new Map<number, Category[]>()
  for (const c of categories) {
    if (c.parent_id !== null) {
      const arr = childMap.get(c.parent_id) || []
      arr.push(c)
      childMap.set(c.parent_id, arr)
    }
  }

  const groupMap = new Map<string, (Category & { children: Category[] })[]>()
  for (const cat of roots) {
    const colonIdx = cat.name.indexOf(':')
    const group = colonIdx > 0 ? cat.name.substring(0, colonIdx).trim() : 'その他'
    if (!groupMap.has(group)) groupMap.set(group, [])
    groupMap.get(group)!.push({
      ...cat,
      children: childMap.get(cat.id) || [],
    })
  }

  return Array.from(groupMap.entries()).map(([groupName, categories]) => ({
    groupName,
    categories,
  }))
}

interface Props {
  selectedIds: number[]
  setSelectedIds: React.Dispatch<React.SetStateAction<number[]>>
  /** 新規トップレベルカテゴリ名（保存時に呼び出し側がAPIへ送る） */
  newCategoryName: string
  setNewCategoryName: (v: string) => void
  /** マウント時にこのプレフィックスで始まる第2層カテゴリを自動展開（例: "USA: "） */
  autoExpandPrefix?: string
}

function CategoryTreeSelector({
  selectedIds,
  setSelectedIds,
  newCategoryName,
  setNewCategoryName,
  autoExpandPrefix,
}: Props) {
  const { data: categories = [], isLoading: categoriesLoading } = useCategories()
  const createCategoryMutation = useCreateCategory()

  const [showNewInput, setShowNewInput] = useState(false)
  // 第3層追加用: どの親カテゴリの下に追加するか
  const [addChildParentId, setAddChildParentId] = useState<number | null>(null)
  const [newChildName, setNewChildName] = useState('')
  // 開閉状態（第2層カテゴリ→子カテゴリの表示切替）
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  const tree = useMemo(() => buildCategoryTree(categories), [categories])

  // 国プレフィックス指定時、該当する第2層カテゴリを自動展開（初回のみ）
  const [didAutoExpand, setDidAutoExpand] = useState(false)
  useEffect(() => {
    if (didAutoExpand || !autoExpandPrefix || categories.length === 0) return
    const toExpand = categories
      .filter(c => c.parent_id === null && c.name.startsWith(autoExpandPrefix))
      .map(c => c.id)
    if (toExpand.length > 0) setExpandedIds(prev => new Set([...prev, ...toExpand]))
    setDidAutoExpand(true)
  }, [autoExpandPrefix, categories, didAutoExpand])

  const toggleExpand = (catId: number) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(catId)) next.delete(catId)
      else next.add(catId)
      return next
    })
  }

  const toggleCategory = (id: number) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const handleAddChild = async (parentId: number) => {
    const name = newChildName.trim()
    if (!name) return
    try {
      const created = await createCategoryMutation.mutateAsync({
        name,
        parent_id: parentId,
      })
      setSelectedIds(prev => [...prev, created.id])
      setNewChildName('')
      setAddChildParentId(null)
      setExpandedIds(prev => new Set(prev).add(parentId))
    } catch (e: any) {
      message.error(e.message || '作成に失敗しました')
    }
  }

  const renderTag = (cat: Category, isChild: boolean = false, hasChildren: boolean = false) => {
    const isSelected = selectedIds.includes(cat.id)
    const shortName = cat.name.includes(':') ? cat.name.split(':')[1].trim() : cat.name
    return (
      <Tag
        key={cat.id}
        color={isSelected ? cat.color : undefined}
        style={{
          cursor: 'pointer',
          borderColor: isSelected ? cat.color : colors.border,
          background: isSelected ? undefined : colors.bgTertiary,
          color: isSelected ? '#fff' : colors.textSecondary,
          fontSize: isChild ? 10 : 11,
          lineHeight: '20px',
          padding: '0 6px',
          margin: 0,
        }}
        onClick={() => {
          toggleCategory(cat.id)
          if (hasChildren) toggleExpand(cat.id)
        }}
      >
        {shortName}
      </Tag>
    )
  }

  return (
    <div style={{ marginBottom: 12 }}>
      <Text style={{ color: colors.textSecondary, fontSize: 12, display: 'block', marginBottom: 8 }}>
        カテゴリ（複数選択可）
      </Text>

      {categoriesLoading ? (
        <div style={{ textAlign: 'center', padding: 12 }}><Spin size="small" /></div>
      ) : categories.length === 0 ? (
        <Text style={{ color: colors.textTertiary, fontSize: 11 }}>
          カテゴリがありません。管理画面から初期投入してください。
        </Text>
      ) : (
        <div style={{ maxHeight: 300, overflowY: 'auto', paddingRight: 4 }}>
          {tree.map(group => (
            <div key={group.groupName} style={{ marginBottom: 10 }}>
              <Text style={{ color: colors.textTertiary, fontSize: 10, display: 'block', marginBottom: 4 }}>
                {group.groupName}
              </Text>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {group.categories.map(cat => {
                  const hasChildren = cat.children.length > 0
                  const isExpanded = expandedIds.has(cat.id)

                  return (
                    <div key={cat.id}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        {hasChildren ? (
                          <span
                            onClick={() => toggleExpand(cat.id)}
                            style={{
                              cursor: 'pointer',
                              color: colors.textTertiary,
                              fontSize: 9,
                              width: 14,
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              flexShrink: 0,
                            }}
                          >
                            {isExpanded ? <DownOutlined /> : <RightOutlined />}
                          </span>
                        ) : (
                          <span style={{ width: 14, flexShrink: 0 }} />
                        )}
                        {renderTag(cat, false, hasChildren)}
                        <span
                          onClick={() => {
                            setAddChildParentId(addChildParentId === cat.id ? null : cat.id)
                            setNewChildName('')
                            if (!expandedIds.has(cat.id)) {
                              setExpandedIds(prev => new Set(prev).add(cat.id))
                            }
                          }}
                          style={{
                            cursor: 'pointer',
                            color: colors.textTertiary,
                            fontSize: 10,
                            padding: '0 2px',
                            opacity: 0.7,
                          }}
                          title="サブカテゴリを追加"
                        >
                          <PlusOutlined />
                        </span>
                      </div>

                      {isExpanded && hasChildren && (
                        <div style={{
                          marginLeft: 18,
                          marginTop: 3,
                          display: 'flex',
                          flexWrap: 'wrap',
                          gap: 3,
                        }}>
                          {cat.children.map(child => renderTag(child, true))}
                        </div>
                      )}

                      {addChildParentId === cat.id && (
                        <div style={{ marginLeft: 18, marginTop: 4, display: 'flex', gap: 4, alignItems: 'center' }}>
                          <Input
                            placeholder="サブカテゴリ名"
                            value={newChildName}
                            onChange={e => setNewChildName(e.target.value)}
                            onPressEnter={() => handleAddChild(cat.id)}
                            style={{
                              background: colors.bgTertiary,
                              borderColor: colors.border,
                              color: '#f1f5f9',
                              width: 160,
                            }}
                            size="small"
                            autoFocus
                          />
                          <Tag
                            style={{
                              cursor: 'pointer',
                              background: colors.accent,
                              color: '#fff',
                              border: 'none',
                              fontSize: 10,
                              lineHeight: '20px',
                              padding: '0 6px',
                              margin: 0,
                            }}
                            onClick={() => handleAddChild(cat.id)}
                          >
                            追加
                          </Tag>
                          <Tag
                            style={{
                              cursor: 'pointer',
                              background: 'transparent',
                              color: colors.textTertiary,
                              borderColor: colors.border,
                              fontSize: 10,
                              lineHeight: '20px',
                              padding: '0 6px',
                              margin: 0,
                            }}
                            onClick={() => { setAddChildParentId(null); setNewChildName('') }}
                          >
                            ×
                          </Tag>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* +新規トップレベルカテゴリ */}
      {!showNewInput && (
        <Tag
          style={{
            cursor: 'pointer',
            borderStyle: 'dashed',
            background: 'transparent',
            color: colors.textSecondary,
            marginTop: 8,
            fontSize: 11,
          }}
          onClick={() => setShowNewInput(true)}
        >
          <PlusOutlined /> 新規カテゴリ
        </Tag>
      )}

      {showNewInput && (
        <div style={{ marginTop: 8 }}>
          <Input
            placeholder="新しいカテゴリ名（例: USA: 貿易）"
            value={newCategoryName}
            onChange={e => setNewCategoryName(e.target.value)}
            style={{ background: colors.bgTertiary, borderColor: colors.border, color: '#f1f5f9' }}
            size="small"
          />
        </div>
      )}
    </div>
  )
}

export default CategoryTreeSelector
