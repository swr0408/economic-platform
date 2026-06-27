/**
 * 手動ヘッドライン作成モーダル (master 限定)
 * 内容を記入し、分類タグ + 保存先カテゴリを選択して登録する。
 * /inbox ページと各国ページの右サイドバーから利用される。
 */
import { useState } from 'react'
import { Modal, Input, Select, Typography, message, Switch } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import { useCreateManualHeadline } from '../../hooks/useHeadlines'
import { useIsMaster } from '../../hooks/useIsMaster'
import CategoryTreeSelector from './CategoryTreeSelector'

const { Text } = Typography

const colors = {
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
  accent: '#10b981',
}

const ROUGH_CATEGORY_OPTIONS = [
  { value: 'central_bank', label: '中央銀行' },
  { value: 'macro', label: 'マクロ' },
  { value: 'oil_energy', label: '原油/エネルギー' },
  { value: 'geopolitics', label: '地政学' },
  { value: 'equities', label: '株式' },
  { value: 'rates_fx', label: '金利/為替' },
  { value: 'other', label: 'その他' },
]

interface Props {
  onClose: () => void
  /** 国サイドバーから開いた場合、該当カテゴリを自動展開（例: "USA: "） */
  defaultCategoryPrefix?: string
}

function ManualHeadlineModal({ onClose, defaultCategoryPrefix }: Props) {
  const createMutation = useCreateManualHeadline()
  const isMaster = useIsMaster()

  const [content, setContent] = useState('')
  const [roughCategory, setRoughCategory] = useState<string | undefined>(undefined)
  const [externalLink, setExternalLink] = useState('')
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [newCategoryName, setNewCategoryName] = useState('')
  const [note, setNote] = useState('')
  const [isPublicVisible, setIsPublicVisible] = useState(false)

  const handleCreate = async () => {
    if (!content.trim()) {
      message.warning('内容を入力してください')
      return
    }
    if (selectedIds.length === 0 && !newCategoryName.trim()) {
      message.warning('保存先カテゴリを選択してください')
      return
    }
    try {
      await createMutation.mutateAsync({
        content: content.trim(),
        roughCategory: roughCategory || undefined,
        categoryIds: selectedIds,
        newCategoryName: newCategoryName.trim() || undefined,
        note: note.trim() || undefined,
        externalLink: externalLink.trim() || undefined,
        isPublicVisible: isMaster ? isPublicVisible : false,
      })
      message.success('登録しました')
      onClose()
    } catch (e: any) {
      message.error(e.message || '登録に失敗しました')
    }
  }

  return (
    <Modal
      title={<span style={{ color: colors.textPrimary, fontSize: 15 }}>ヘッドラインを手動登録</span>}
      open
      onCancel={onClose}
      onOk={handleCreate}
      okText="登録"
      cancelText="キャンセル"
      confirmLoading={createMutation.isPending}
      width={500}
      styles={{
        header: { background: colors.bgSecondary, borderBottom: `1px solid ${colors.border}`, padding: '14px 20px' },
        body: { background: colors.bgSecondary, padding: '16px 20px' },
        footer: { background: colors.bgSecondary, borderTop: `1px solid ${colors.border}`, padding: '10px 20px' },
        wrapper: { background: 'transparent' },
        mask: { backdropFilter: 'blur(4px)' },
      }}
      closeIcon={<span style={{ color: colors.textSecondary, fontSize: 16 }}>×</span>}
    >
      {/* Content */}
      <div style={{ marginBottom: 12 }}>
        <Text style={{ color: colors.textSecondary, fontSize: 12, display: 'block', marginBottom: 4 }}>
          内容
        </Text>
        <Input.TextArea
          autoSize={{ minRows: 3, maxRows: 12 }}
          placeholder="ヘッドラインの内容を入力...（改行はそのまま保存・表示されます）"
          value={content}
          onChange={e => setContent(e.target.value)}
          style={{ background: colors.bgTertiary, borderColor: colors.border, color: colors.textPrimary }}
          autoFocus
        />
      </div>

      {/* Rough category tag */}
      <div style={{ marginBottom: 12 }}>
        <Text style={{ color: colors.textSecondary, fontSize: 12, display: 'block', marginBottom: 4 }}>
          分類タグ（任意）
        </Text>
        <Select
          value={roughCategory}
          onChange={setRoughCategory}
          options={ROUGH_CATEGORY_OPTIONS}
          placeholder="分類を選択"
          allowClear
          style={{ width: 200 }}
          popupMatchSelectWidth={false}
        />
      </div>

      {/* External link */}
      <div style={{ marginBottom: 12 }}>
        <Text style={{ color: colors.textSecondary, fontSize: 12, display: 'block', marginBottom: 4 }}>
          リンク（任意）
        </Text>
        <Input
          placeholder="https://..."
          value={externalLink}
          onChange={e => setExternalLink(e.target.value)}
          style={{ background: colors.bgTertiary, borderColor: colors.border, color: colors.textPrimary }}
          size="small"
        />
      </div>

      {/* Save target category selection */}
      <CategoryTreeSelector
        selectedIds={selectedIds}
        setSelectedIds={setSelectedIds}
        newCategoryName={newCategoryName}
        setNewCategoryName={setNewCategoryName}
        autoExpandPrefix={defaultCategoryPrefix}
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
          <Switch size="small" checked={isPublicVisible} onChange={setIsPublicVisible} />
        </div>
      )}
    </Modal>
  )
}

export default ManualHeadlineModal
