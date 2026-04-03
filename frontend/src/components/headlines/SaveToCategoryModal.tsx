import { useState, useMemo } from 'react'
import { Modal, Input, Tag, Typography, message, Spin } from 'antd'
import { PlusOutlined, RightOutlined, DownOutlined } from '@ant-design/icons'
import { useCategories, useSaveHeadline, useCreateCategory } from '../../hooks/useHeadlines'
import type { Headline, Category } from '../../api/headlinesApi'

const { Text } = Typography

const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
  accent: '#10b981',
}

interface Props {
  headline: Headline
  onClose: () => void
}

/** 国グループ → カテゴリ → 子カテゴリ のツリー構造 */
interface CategoryGroup {
  groupName: string
  /** 第2層: parent_id = null のカテゴリ */
  categories: (Category & { children: Category[] })[]
}

function buildCategoryTree(categories: Category[]): CategoryGroup[] {
  // parent_id が null のカテゴリ（第2層）
  const roots = categories.filter(c => c.parent_id === null)
  // parent_id がある子カテゴリ（第3層）
  const childMap = new Map<number, Category[]>()
  for (const c of categories) {
    if (c.parent_id !== null) {
      const arr = childMap.get(c.parent_id) || []
      arr.push(c)
      childMap.set(c.parent_id, arr)
    }
  }

  // 国グループでまとめる
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

function SaveToCategoryModal({ headline, onClose }: Props) {
  const { data: categories = [], isLoading: categoriesLoading } = useCategories()
  const saveMutation = useSaveHeadline()
  const createCategoryMutation = useCreateCategory()
  const [selectedIds, setSelectedIds] = useState<number[]>(
    headline.saved_categories?.map(sc => sc.category_id) || []
  )
  const [newCategoryName, setNewCategoryName] = useState('')
  const [note, setNote] = useState('')
  const [showNewInput, setShowNewInput] = useState(false)
  // 第3層追加用: どの親カテゴリの下に追加するか
  const [addChildParentId, setAddChildParentId] = useState<number | null>(null)
  const [newChildName, setNewChildName] = useState('')
  // 開閉状態（第2層カテゴリ→子カテゴリの表示切替）- 第2層タグクリックで展開
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  const tree = useMemo(() => buildCategoryTree(categories), [categories])

  const toggleExpand = (catId: number) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(catId)) next.delete(catId)
      else next.add(catId)
      return next
    })
  }

  const handleSave = async () => {
    if (selectedIds.length === 0 && !newCategoryName.trim()) {
      message.warning('カテゴリを選択してください')
      return
    }
    try {
      await saveMutation.mutateAsync({
        headlineId: headline.id,
        params: {
          categoryIds: selectedIds,
          newCategoryName: newCategoryName.trim() || undefined,
          note: note.trim() || undefined,
        },
      })
      message.success('保存しました')
      onClose()
    } catch (e: any) {
      message.error(e.message || '保存に失敗しました')
    }
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
      // 自動展開
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
          // 第2層タグクリック時に子カテゴリを展開/折りたたみ
          if (hasChildren) {
            toggleExpand(cat.id)
          }
        }}
      >
        {shortName}
      </Tag>
    )
  }

  return (
    <Modal
      title={
        <span style={{ color: colors.textPrimary, fontSize: 15 }}>
          カテゴリに保存
        </span>
      }
      open
      onCancel={onClose}
      onOk={handleSave}
      okText="保存"
      cancelText="キャンセル"
      confirmLoading={saveMutation.isPending}
      width={500}
      styles={{
        header: {
          background: colors.bgSecondary,
          borderBottom: `1px solid ${colors.border}`,
          padding: '14px 20px',
        },
        body: {
          background: colors.bgSecondary,
          padding: '16px 20px',
        },
        footer: {
          background: colors.bgSecondary,
          borderTop: `1px solid ${colors.border}`,
          padding: '10px 20px',
        },
        wrapper: {
          background: 'transparent',
        },
        mask: {
          backdropFilter: 'blur(4px)',
        },
      }}
      closeIcon={<span style={{ color: colors.textSecondary, fontSize: 16 }}>×</span>}
    >
      {/* Headline preview */}
      <div style={{
        background: colors.bgTertiary,
        borderRadius: 6,
        padding: '8px 12px',
        marginBottom: 16,
        border: `1px solid ${colors.border}`,
        maxHeight: 80,
        overflowY: 'auto',
      }}>
        <Text style={{ color: colors.textPrimary, fontSize: 12, lineHeight: 1.5 }}>
          {headline.headline_ja || headline.headline_raw}
        </Text>
      </div>

      {/* Category selection */}
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
          <div style={{
            maxHeight: 300,
            overflowY: 'auto',
            paddingRight: 4,
          }}>
            {tree.map(group => (
              <div key={group.groupName} style={{ marginBottom: 10 }}>
                {/* 国グループ名 (第1層) */}
                <Text style={{ color: colors.textTertiary, fontSize: 10, display: 'block', marginBottom: 4 }}>
                  {group.groupName}
                </Text>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {group.categories.map(cat => {
                    const hasChildren = cat.children.length > 0
                    const isExpanded = expandedIds.has(cat.id)

                    return (
                      <div key={cat.id}>
                        {/* 第2層カテゴリ */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          {/* 開閉トグル (子がある場合のみ) */}
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
                          {/* + ボタン（子カテゴリ追加） */}
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

                        {/* 第3層: 子カテゴリ (開閉式) */}
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

                        {/* 新規子カテゴリ入力 */}
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
                                color: colors.textPrimary,
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
      </div>

      {/* New top-level category name */}
      {showNewInput && (
        <div style={{ marginBottom: 12 }}>
          <Input
            placeholder="新しいカテゴリ名（例: USA: 貿易）"
            value={newCategoryName}
            onChange={e => setNewCategoryName(e.target.value)}
            style={{ background: colors.bgTertiary, borderColor: colors.border, color: colors.textPrimary }}
            size="small"
          />
        </div>
      )}

      {/* Note */}
      <div>
        <Text style={{ color: colors.textSecondary, fontSize: 12, display: 'block', marginBottom: 4 }}>
          メモ（任意）
        </Text>
        <Input.TextArea
          rows={2}
          placeholder="メモを追加..."
          value={note}
          onChange={e => setNote(e.target.value)}
          style={{ background: colors.bgTertiary, borderColor: colors.border, color: colors.textPrimary }}
        />
      </div>
    </Modal>
  )
}

export default SaveToCategoryModal
