import { useState } from 'react'
import { Modal, Input, Tag, Typography, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useCategories, useSaveHeadline } from '../../hooks/useHeadlines'
import type { Headline } from '../../api/headlinesApi'

const { Text } = Typography

const colors = {
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
  accent: '#10b981',
}

interface Props {
  headline: Headline
  onClose: () => void
}

function SaveToCategoryModal({ headline, onClose }: Props) {
  const { data: categories = [] } = useCategories()
  const saveMutation = useSaveHeadline()
  const [selectedIds, setSelectedIds] = useState<number[]>(
    headline.saved_categories?.map(sc => sc.category_id) || []
  )
  const [newCategoryName, setNewCategoryName] = useState('')
  const [note, setNote] = useState('')
  const [showNewInput, setShowNewInput] = useState(false)

  const handleSave = async () => {
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

  return (
    <Modal
      title="カテゴリに保存"
      open
      onCancel={onClose}
      onOk={handleSave}
      okText="保存"
      cancelText="キャンセル"
      confirmLoading={saveMutation.isPending}
      width={420}
    >
      {/* Headline preview */}
      <div style={{
        background: colors.bgTertiary,
        borderRadius: 6,
        padding: '8px 12px',
        marginBottom: 16,
        border: `1px solid ${colors.border}`,
      }}>
        <Text style={{ color: colors.textPrimary, fontSize: 12 }}>
          {headline.headline_ja || headline.headline_raw}
        </Text>
      </div>

      {/* Category selection */}
      <div style={{ marginBottom: 12 }}>
        <Text style={{ color: colors.textSecondary, fontSize: 12, display: 'block', marginBottom: 8 }}>
          カテゴリ（複数選択可）
        </Text>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {categories.map(cat => (
            <Tag
              key={cat.id}
              color={selectedIds.includes(cat.id) ? cat.color : undefined}
              style={{
                cursor: 'pointer',
                borderColor: selectedIds.includes(cat.id) ? cat.color : colors.border,
                background: selectedIds.includes(cat.id) ? undefined : colors.bgTertiary,
                color: selectedIds.includes(cat.id) ? '#fff' : colors.textSecondary,
              }}
              onClick={() => toggleCategory(cat.id)}
            >
              {cat.name}
            </Tag>
          ))}
          {!showNewInput && (
            <Tag
              style={{ cursor: 'pointer', borderStyle: 'dashed', background: 'transparent', color: colors.textSecondary }}
              onClick={() => setShowNewInput(true)}
            >
              <PlusOutlined /> 新規
            </Tag>
          )}
        </div>
      </div>

      {/* New category name */}
      {showNewInput && (
        <div style={{ marginBottom: 12 }}>
          <Input
            placeholder="新しいカテゴリ名"
            value={newCategoryName}
            onChange={e => setNewCategoryName(e.target.value)}
            style={{ background: colors.bgTertiary, borderColor: colors.border }}
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
          style={{ background: colors.bgTertiary, borderColor: colors.border }}
        />
      </div>
    </Modal>
  )
}

export default SaveToCategoryModal
