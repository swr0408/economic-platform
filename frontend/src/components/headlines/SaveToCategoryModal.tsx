import { useState } from 'react'
import { Modal, Input, Typography, message, Switch } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import { useSaveHeadline } from '../../hooks/useHeadlines'
import { useIsMaster } from '../../hooks/useIsMaster'
import CategoryTreeSelector from './CategoryTreeSelector'
import type { Headline } from '../../api/headlinesApi'

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

function SaveToCategoryModal({ headline, onClose }: Props) {
  const saveMutation = useSaveHeadline()
  const isMaster = useIsMaster()
  const [selectedIds, setSelectedIds] = useState<number[]>(
    headline.saved_categories?.map(sc => sc.category_id) || []
  )
  const [newCategoryName, setNewCategoryName] = useState('')
  const [note, setNote] = useState('')
  // 一般公開フラグ (master のみ操作可能)
  const [isPublicVisible, setIsPublicVisible] = useState(false)

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
          isPublicVisible: isMaster ? isPublicVisible : false,
        },
      })
      message.success('保存しました')
      onClose()
    } catch (e: any) {
      message.error(e.message || '保存に失敗しました')
    }
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
      <CategoryTreeSelector
        selectedIds={selectedIds}
        setSelectedIds={setSelectedIds}
        newCategoryName={newCategoryName}
        setNewCategoryName={setNewCategoryName}
      />

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

      {/* Public visibility toggle (master only) */}
      {isMaster && (
        <div style={{
          marginTop: 12,
          padding: '8px 12px',
          background: colors.bgTertiary,
          borderRadius: 6,
          border: `1px solid ${colors.border}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <GlobalOutlined style={{ color: isPublicVisible ? colors.accent : colors.textTertiary, fontSize: 14 }} />
            <div>
              <Text style={{ color: colors.textPrimary, fontSize: 12, display: 'block' }}>
                一般公開
              </Text>
              <Text style={{ color: colors.textTertiary, fontSize: 10 }}>
                すべてのユーザー (general/special) がこのヘッドラインを閲覧できます
              </Text>
            </div>
          </div>
          <Switch
            size="small"
            checked={isPublicVisible}
            onChange={setIsPublicVisible}
          />
        </div>
      )}
    </Modal>
  )
}

export default SaveToCategoryModal
