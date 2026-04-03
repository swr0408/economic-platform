import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Typography, Tag, Button, Empty, Spin, Tooltip, Popconfirm, Input,
  ColorPicker, message, Modal,
} from 'antd'
import {
  FolderOutlined, StarFilled, DeleteOutlined, EditOutlined,
  PlusOutlined, LinkOutlined, MinusCircleOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  useHeadlines, useCategories, useUnsaveHeadline,
  useCreateCategory, useDeleteCategory,
} from '../hooks/useHeadlines'
import type { Category, Headline } from '../api/headlinesApi'

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

/** カテゴリを国グループ→親→子のツリーで整理 */
interface CategoryNode {
  category: Category
  children: Category[]
}
interface CategoryGroup {
  groupName: string
  nodes: CategoryNode[]
}

function buildCategoryGroups(categories: Category[]): CategoryGroup[] {
  const roots = categories.filter(c => c.parent_id === null)
  const childMap = new Map<number, Category[]>()
  for (const c of categories) {
    if (c.parent_id !== null) {
      const arr = childMap.get(c.parent_id) || []
      arr.push(c)
      childMap.set(c.parent_id, arr)
    }
  }

  const groupMap = new Map<string, CategoryNode[]>()
  for (const cat of roots) {
    const colonIdx = cat.name.indexOf(':')
    const group = colonIdx > 0 ? cat.name.substring(0, colonIdx).trim() : 'その他'
    if (!groupMap.has(group)) groupMap.set(group, [])
    groupMap.get(group)!.push({
      category: cat,
      children: childMap.get(cat.id) || [],
    })
  }

  return Array.from(groupMap.entries()).map(([groupName, nodes]) => ({
    groupName,
    nodes,
  }))
}

function HeadlinesSavedPage() {
  const { categoryId } = useParams<{ categoryId?: string }>()
  const navigate = useNavigate()
  const { data: categories = [], isLoading: catLoading } = useCategories()
  const selectedCatId = categoryId ? parseInt(categoryId) : null

  const groups = buildCategoryGroups(categories)

  if (catLoading) {
    return <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography.Title level={4} style={{ color: colors.textPrimary, margin: 0 }}>
          <FolderOutlined style={{ marginRight: 8, color: colors.accent }} />
          保存済みヘッドライン
        </Typography.Title>
      </div>

      {/* Category tabs - 階層表示 */}
      <div style={{
        marginBottom: 16,
        background: colors.bgSecondary, borderRadius: 8, padding: '12px 16px',
        border: `1px solid ${colors.border}`,
      }}>
        {/* すべてボタン */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
          <Tag
            style={{
              cursor: 'pointer',
              background: !selectedCatId ? colors.accent : colors.bgTertiary,
              color: !selectedCatId ? '#fff' : colors.textSecondary,
              borderColor: !selectedCatId ? colors.accent : colors.border,
              fontSize: 12,
            }}
            onClick={() => navigate('/saved')}
          >
            すべて
          </Tag>
        </div>

        {/* 国グループごとに表示 */}
        {groups.map(group => (
          <div key={group.groupName} style={{ marginBottom: 8 }}>
            <Text style={{ color: colors.textTertiary, fontSize: 10, display: 'block', marginBottom: 4 }}>
              {group.groupName}
            </Text>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {group.nodes.map(node => {
                const cat = node.category
                const shortName = cat.name.includes(':') ? cat.name.split(':')[1].trim() : cat.name
                const totalCount = cat.headline_count + node.children.reduce((sum, c) => sum + c.headline_count, 0)

                return (
                  <div key={cat.id}>
                    {/* 第2層 カテゴリ */}
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
                      <Tag
                        style={{
                          cursor: 'pointer',
                          background: selectedCatId === cat.id ? cat.color : colors.bgTertiary,
                          color: selectedCatId === cat.id ? '#fff' : colors.textSecondary,
                          borderColor: selectedCatId === cat.id ? cat.color : colors.border,
                          fontSize: 11,
                        }}
                        onClick={() => navigate(selectedCatId === cat.id ? '/saved' : `/saved/${cat.id}`)}
                      >
                        {shortName} ({totalCount})
                      </Tag>

                      {/* 第3層 子カテゴリ */}
                      {node.children.map(child => (
                        <Tag
                          key={child.id}
                          style={{
                            cursor: 'pointer',
                            background: selectedCatId === child.id ? child.color : 'transparent',
                            color: selectedCatId === child.id ? '#fff' : colors.textTertiary,
                            borderColor: selectedCatId === child.id ? child.color : colors.border,
                            borderStyle: 'dashed',
                            fontSize: 10,
                          }}
                          onClick={() => navigate(selectedCatId === child.id ? '/saved' : `/saved/${child.id}`)}
                        >
                          {child.name} ({child.headline_count})
                        </Tag>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}

        <CategoryManager categories={categories} />
      </div>

      {/* Saved headlines list */}
      <SavedHeadlinesList categoryId={selectedCatId} />
    </div>
  )
}

// ========== SavedHeadlinesList ==========

function SavedHeadlinesList({ categoryId }: { categoryId: number | null }) {
  const params = categoryId
    ? { savedOnly: true, savedCategoryId: categoryId, limit: 50 }
    : { savedOnly: true, limit: 50 }
  const { data, isLoading } = useHeadlines(params)
  const unsaveMutation = useUnsaveHeadline()
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)

  if (isLoading) {
    return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  }

  const items = data?.items || []

  if (items.length === 0) {
    return <Empty description="保存済みヘッドラインがありません" style={{ padding: 40 }} />
  }

  const handleDelete = (headlineId: number, savedId: number) => {
    if (confirmDeleteId === savedId) {
      unsaveMutation.mutate({ headlineId, savedId })
      setConfirmDeleteId(null)
    } else {
      setConfirmDeleteId(savedId)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {items.map((item: Headline) => (
        <div
          key={item.id}
          style={{
            background: colors.bgSecondary,
            borderRadius: 6,
            padding: '10px 14px',
            border: `1px solid ${colors.border}`,
            display: 'flex',
            gap: 10,
            alignItems: 'flex-start',
          }}
          onMouseLeave={() => setConfirmDeleteId(null)}
        >
          <StarFilled style={{ color: '#f59e0b', fontSize: 14, marginTop: 3 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ color: colors.textPrimary, fontSize: 13, lineHeight: 1.5 }}>
              {item.headline_ja || item.headline_raw}
            </div>
            {item.headline_ja && (
              <div style={{ color: colors.textTertiary, fontSize: 11, marginTop: 2 }}>
                {item.headline_raw}
              </div>
            )}
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 4, flexWrap: 'wrap' }}>
              <Text style={{ color: colors.textTertiary, fontSize: 10 }}>
                {item.published_at ? dayjs(item.published_at).format('YYYY/MM/DD HH:mm') : ''}
              </Text>
              {item.speaker_name && (
                <Text style={{ color: colors.accent, fontSize: 11 }}>{item.speaker_name}</Text>
              )}
              {item.external_link && (
                <a href={item.external_link} target="_blank" rel="noopener noreferrer" style={{ color: colors.textTertiary, fontSize: 11 }}>
                  <LinkOutlined /> リンク
                </a>
              )}
              {item.saved_categories?.map(sc => (
                <span key={sc.saved_id} style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
                  <Tag color={sc.category_color} style={{ margin: 0, fontSize: 10 }}>
                    {sc.category_name}
                    {sc.note && <Tooltip title={sc.note}> *</Tooltip>}
                  </Tag>
                  <MinusCircleOutlined
                    onClick={() => handleDelete(item.id, sc.saved_id)}
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
            {confirmDeleteId !== null && item.saved_categories?.some(sc => sc.saved_id === confirmDeleteId) && (
              <div style={{ marginTop: 4, fontSize: 10, color: '#ef4444', display: 'flex', alignItems: 'center', gap: 6 }}>
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
        </div>
      ))}
    </div>
  )
}

// ========== Category Manager ==========

function CategoryManager({ categories }: { categories: Category[] }) {
  const [open, setOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState('#3b82f6')
  const createMutation = useCreateCategory()
  const deleteMutation = useDeleteCategory()

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      await createMutation.mutateAsync({ name: newName.trim(), color: newColor })
      setNewName('')
      message.success('カテゴリを作成しました')
    } catch (e: any) {
      message.error(e.message)
    }
  }

  return (
    <>
      <Tag
        style={{ cursor: 'pointer', borderStyle: 'dashed', background: 'transparent', color: colors.textSecondary, marginTop: 8 }}
        onClick={() => setOpen(true)}
      >
        <EditOutlined /> 管理
      </Tag>
      <Modal
        title="カテゴリ管理"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width={400}
      >
        {/* Existing categories */}
        <div style={{ marginBottom: 16 }}>
          {categories.map(cat => (
            <div key={cat.id} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <div style={{ width: 16, height: 16, borderRadius: 4, background: cat.color }} />
              <Text style={{ flex: 1, color: colors.textPrimary }}>{cat.name}</Text>
              <Text style={{ color: colors.textSecondary, fontSize: 11 }}>{cat.headline_count}件</Text>
              <Popconfirm
                title="このカテゴリを削除しますか？"
                onConfirm={() => deleteMutation.mutate(cat.id)}
                okText="削除"
                cancelText="キャンセル"
              >
                <Button type="text" size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            </div>
          ))}
          {categories.length === 0 && (
            <Text style={{ color: colors.textSecondary }}>カテゴリがありません</Text>
          )}
        </div>

        {/* Create new */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Input
            placeholder="新しいカテゴリ"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onPressEnter={handleCreate}
            style={{ flex: 1 }}
            size="small"
          />
          <ColorPicker
            value={newColor}
            onChange={(_, hex) => setNewColor(hex)}
            size="small"
          />
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={handleCreate}
            loading={createMutation.isPending}
          >
            追加
          </Button>
        </div>
      </Modal>
    </>
  )
}

export default HeadlinesSavedPage
