import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Typography, Tag, Button, Empty, Spin, Space, Tooltip, Popconfirm, Input,
  ColorPicker, message, Modal,
} from 'antd'
import {
  FolderOutlined, StarFilled, DeleteOutlined, EditOutlined,
  PlusOutlined, LinkOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/ja'
import {
  useHeadlines, useCategories, useUnsaveHeadline,
  useCreateCategory, useDeleteCategory,
} from '../hooks/useHeadlines'
import type { Category } from '../api/headlinesApi'

dayjs.extend(relativeTime)
dayjs.locale('ja')

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

function HeadlinesSavedPage() {
  const { categoryId } = useParams<{ categoryId?: string }>()
  const navigate = useNavigate()
  const { data: categories = [], isLoading: catLoading } = useCategories()
  const selectedCatId = categoryId ? parseInt(categoryId) : null

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

      {/* Category tabs */}
      <div style={{
        display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16,
        background: colors.bgSecondary, borderRadius: 8, padding: '12px 16px',
        border: `1px solid ${colors.border}`,
      }}>
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
        {categories.map(cat => (
          <Tag
            key={cat.id}
            style={{
              cursor: 'pointer',
              background: selectedCatId === cat.id ? cat.color : colors.bgTertiary,
              color: selectedCatId === cat.id ? '#fff' : colors.textSecondary,
              borderColor: selectedCatId === cat.id ? cat.color : colors.border,
              fontSize: 12,
            }}
            onClick={() => navigate(`/saved/${cat.id}`)}
          >
            {cat.name} ({cat.headline_count})
          </Tag>
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
    ? { savedOnly: true, limit: 50 }
    : { savedOnly: true, limit: 50 }
  // Note: backend filters by savedOnly; category filtering is done client-side for now
  const { data, isLoading } = useHeadlines(params)
  const unsaveMutation = useUnsaveHeadline()

  if (isLoading) {
    return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  }

  const items = data?.items || []
  const filtered = categoryId
    ? items.filter(h => h.saved_categories?.some(sc => sc.category_id === categoryId))
    : items

  if (filtered.length === 0) {
    return <Empty description="保存済みヘッドラインがありません" style={{ padding: 40 }} />
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {filtered.map(item => (
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
              {item.speaker_name && (
                <Text style={{ color: colors.accent, fontSize: 11 }}>{item.speaker_name}</Text>
              )}
              {item.external_link && (
                <a href={item.external_link} target="_blank" rel="noopener noreferrer" style={{ color: colors.textTertiary, fontSize: 11 }}>
                  <LinkOutlined /> リンク
                </a>
              )}
              {item.saved_categories?.map(sc => (
                <Tag key={sc.saved_id} color={sc.category_color} style={{ margin: 0, fontSize: 10 }}>
                  {sc.category_name}
                  {sc.note && <Tooltip title={sc.note}> *</Tooltip>}
                </Tag>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-end', minWidth: 80 }}>
            <Text style={{ color: colors.textTertiary, fontSize: 11 }}>
              {item.published_at ? dayjs(item.published_at).format('MM/DD HH:mm') : ''}
            </Text>
            <Space size={2}>
              {item.saved_categories?.map(sc => (
                <Popconfirm
                  key={sc.saved_id}
                  title="保存を解除しますか？"
                  onConfirm={() => unsaveMutation.mutate({ headlineId: item.id, savedId: sc.saved_id })}
                  okText="解除"
                  cancelText="キャンセル"
                >
                  <Button type="text" size="small" icon={<DeleteOutlined />}
                    style={{ color: colors.textTertiary, padding: '0 4px' }} />
                </Popconfirm>
              ))}
            </Space>
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
        style={{ cursor: 'pointer', borderStyle: 'dashed', background: 'transparent', color: colors.textSecondary }}
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
