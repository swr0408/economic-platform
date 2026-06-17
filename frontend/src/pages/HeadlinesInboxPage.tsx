import { useState, useMemo } from 'react'
import { Input, Select, Tag, Button, Pagination, Spin, Space, DatePicker, Switch, Typography, Tooltip, Empty, message } from 'antd'
import {
  SearchOutlined, ReloadOutlined, SoundOutlined,
  StarOutlined, StarFilled, TranslationOutlined, LinkOutlined,
  SettingOutlined, FolderOutlined, PlusOutlined,
  CheckOutlined, CheckCircleFilled,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/ja'
import { useHeadlines, useRetranslate, useReadMarker, useSetReadMarker, useClearReadMarker } from '../hooks/useHeadlines'
import { useIsMaster } from '../hooks/useIsMaster'
import SaveToCategoryModal from '../components/headlines/SaveToCategoryModal'
import ManualHeadlineModal from '../components/headlines/ManualHeadlineModal'
import type { Headline } from '../api/headlinesApi'

dayjs.extend(relativeTime)
dayjs.locale('ja')

const { Text } = Typography
const { RangePicker } = DatePicker

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

const CATEGORY_OPTIONS = [
  { value: '', label: '全カテゴリ' },
  { value: 'central_bank', label: '中央銀行' },
  { value: 'macro', label: 'マクロ' },
  { value: 'oil_energy', label: '原油/エネルギー' },
  { value: 'geopolitics', label: '地政学' },
  { value: 'equities', label: '株式' },
  { value: 'rates_fx', label: '金利/為替' },
  { value: 'other', label: 'その他' },
]

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

function HeadlinesInboxPage() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(30)
  const [roughCategory, setRoughCategory] = useState('')
  const [savedOnly, setSavedOnly] = useState(false)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)
  const [saveModalTarget, setSaveModalTarget] = useState<Headline | null>(null)
  const [manualOpen, setManualOpen] = useState(false)
  const isMaster = useIsMaster()

  const params = useMemo(() => ({
    limit: pageSize,
    offset: (page - 1) * pageSize,
    roughCategory: roughCategory || undefined,
    savedOnly: savedOnly || undefined,
    q: search || undefined,
    from: dateRange?.[0]?.format('YYYY-MM-DD') || undefined,
    to: dateRange?.[1]?.format('YYYY-MM-DD') || undefined,
  }), [page, pageSize, roughCategory, savedOnly, search, dateRange])

  const navigate = useNavigate()
  const { data, isLoading, refetch, isFetching } = useHeadlines(params)
  const retranslate = useRetranslate()

  // 既読マーカー「ここまで見た」(master 限定)
  const { data: readMarker } = useReadMarker(isMaster)
  const setMarkerMutation = useSetReadMarker()
  const clearMarkerMutation = useClearReadMarker()
  const markerTime = isMaster && readMarker?.marked_published_at
    ? dayjs(readMarker.marked_published_at).valueOf()
    : null
  const isReadItem = (item: Headline) =>
    markerTime !== null && !!item.published_at && dayjs(item.published_at).valueOf() <= markerTime
  const firstReadIdx = data ? data.items.findIndex(isReadItem) : -1

  const handleSearch = () => {
    setSearch(searchInput)
    setPage(1)
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Typography.Title level={4} style={{ color: colors.textPrimary, margin: 0 }}>
            <SoundOutlined style={{ marginRight: 8, color: colors.accent }} />
            ヘッドライン
          </Typography.Title>
          <Text style={{ color: colors.textSecondary, fontSize: 12 }}>
            {data ? `${data.total}件` : ''}
          </Text>
        </div>
        <Space size={8}>
          {isMaster && (
            <Button
              icon={<PlusOutlined />}
              onClick={() => setManualOpen(true)}
              style={{ background: colors.accent, borderColor: colors.accent, color: '#fff' }}
            >
              手動登録
            </Button>
          )}
          <Button
            icon={<FolderOutlined />}
            onClick={() => navigate('/saved')}
            style={{ background: colors.bgTertiary, borderColor: colors.border, color: colors.textPrimary }}
          >
            保存済み
          </Button>
          <Button
            icon={<SettingOutlined />}
            onClick={() => navigate('/admin/headlines')}
            style={{ background: colors.bgTertiary, borderColor: colors.border, color: colors.textPrimary }}
          >
            管理
          </Button>
          <Button
            icon={<ReloadOutlined spin={isFetching} />}
            onClick={() => refetch()}
            style={{ background: colors.bgTertiary, borderColor: colors.border, color: colors.textPrimary }}
          >
            更新
          </Button>
        </Space>
      </div>

      {/* Filters */}
      <div style={{
        background: colors.bgSecondary,
        borderRadius: 8,
        padding: '12px 16px',
        marginBottom: 16,
        border: `1px solid ${colors.border}`,
      }}>
        <Space wrap size={8} style={{ width: '100%' }}>
          <Input
            prefix={<SearchOutlined style={{ color: colors.textTertiary }} />}
            placeholder="検索..."
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 200, background: colors.bgTertiary, borderColor: colors.border }}
            allowClear
            onClear={() => { setSearchInput(''); setSearch(''); setPage(1) }}
          />
          <Select
            value={roughCategory}
            onChange={v => { setRoughCategory(v); setPage(1) }}
            options={CATEGORY_OPTIONS}
            style={{ width: 140 }}
            popupMatchSelectWidth={false}
          />
          <RangePicker
            value={dateRange as any}
            onChange={(dates) => { setDateRange(dates as any); setPage(1) }}
            style={{ background: colors.bgTertiary, borderColor: colors.border }}
            allowClear
            size="middle"
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Switch size="small" checked={savedOnly} onChange={v => { setSavedOnly(v); setPage(1) }} />
            <Text style={{ color: colors.textSecondary, fontSize: 12 }}>保存済みのみ</Text>
          </div>
        </Space>
      </div>

      {/* List */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
      ) : !data || data.items.length === 0 ? (
        <Empty description="ヘッドラインがありません" style={{ padding: 60 }} />
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {data.items.map((item, idx) => (
              <div key={item.id} style={{ display: 'contents' }}>
                {/* 「ここまで見た」境界線 (未読→既読の切り替わり位置) */}
                {isMaster && firstReadIdx === idx && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 4px' }}>
                    <div style={{ flex: 1, height: 1, background: `${colors.accent}66` }} />
                    <Text style={{ color: colors.accent, fontSize: 11, whiteSpace: 'nowrap' }}>
                      <CheckOutlined style={{ marginRight: 4 }} />
                      ここまで見た
                      {readMarker?.marked_published_at && ` (${dayjs(readMarker.marked_published_at).format('MM/DD HH:mm')})`}
                    </Text>
                    <div style={{ flex: 1, height: 1, background: `${colors.accent}66` }} />
                  </div>
                )}
                <HeadlineRow
                  item={item}
                  onSave={() => setSaveModalTarget(item)}
                  onRetranslate={() => retranslate.mutate(item.id, {
                    onSuccess: (res) => {
                      if (res.success) message.success('再翻訳しました')
                      else message.warning('翻訳に失敗しました。バックグラウンドで再試行します')
                    },
                    onError: () => message.error('再翻訳リクエストに失敗しました'),
                  })}
                  retranslating={retranslate.isPending && retranslate.variables === item.id}
                  isRead={isMaster && isReadItem(item)}
                  isMarkerHere={isMaster && readMarker?.headline_id === item.id}
                  onMarkRead={isMaster ? () => setMarkerMutation.mutate(item.id) : undefined}
                  onClearMark={isMaster ? () => clearMarkerMutation.mutate() : undefined}
                />
              </div>
            ))}
          </div>

          {/* Pagination */}
          <div style={{ marginTop: 16, textAlign: 'center' }}>
            <Pagination
              current={page}
              pageSize={pageSize}
              total={data.total}
              onChange={(p, ps) => { setPage(p); if (ps !== pageSize) setPageSize(ps) }}
              showSizeChanger
              pageSizeOptions={['20', '30', '50', '100']}
              showTotal={(total) => `${total}件`}
              size="small"
            />
          </div>
        </>
      )}

      {/* Save Modal */}
      {saveModalTarget && (
        <SaveToCategoryModal
          headline={saveModalTarget}
          onClose={() => setSaveModalTarget(null)}
        />
      )}

      {/* Manual Headline Modal (master only) */}
      {manualOpen && isMaster && (
        <ManualHeadlineModal onClose={() => setManualOpen(false)} />
      )}
    </div>
  )
}

// ========== HeadlineRow ==========

function HeadlineRow({
  item,
  onSave,
  onRetranslate,
  retranslating = false,
  isRead = false,
  isMarkerHere = false,
  onMarkRead,
  onClearMark,
}: {
  item: Headline
  onSave: () => void
  onRetranslate: () => void
  retranslating?: boolean
  isRead?: boolean
  isMarkerHere?: boolean
  onMarkRead?: () => void
  onClearMark?: () => void
}) {
  const hasSaved = item.saved_categories && item.saved_categories.length > 0
  const timeAgo = item.published_at ? dayjs(item.published_at).fromNow() : ''
  const publishedTime = item.published_at ? dayjs(item.published_at).format('MM/DD HH:mm') : ''

  return (
    <div
      style={{
        background: colors.bgSecondary,
        borderRadius: 6,
        padding: '10px 14px',
        border: `1px solid ${colors.border}`,
        display: 'flex',
        gap: 10,
        alignItems: 'flex-start',
        transition: 'border-color 0.15s',
        opacity: isRead ? 0.55 : 1,
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = colors.accent + '60')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = colors.border)}
    >
      {/* Left: category badge */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 60, paddingTop: 2 }}>
        {item.rough_category && (
          <Tag
            color={CATEGORY_COLORS[item.rough_category] || '#64748b'}
            style={{ margin: 0, fontSize: 10, lineHeight: '18px', padding: '0 4px', borderColor: 'transparent' }}
          >
            {CATEGORY_LABELS[item.rough_category] || item.rough_category}
          </Tag>
        )}
      </div>

      {/* Center: headline text */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Japanese translation */}
        <div style={{ color: colors.textPrimary, fontSize: 13, lineHeight: 1.5, wordBreak: 'break-word' }}>
          {item.headline_ja || item.headline_raw}
        </div>
        {/* Original (if translated) */}
        {item.headline_ja && (
          <div style={{ color: colors.textTertiary, fontSize: 11, lineHeight: 1.4, marginTop: 2 }}>
            {item.headline_raw}
          </div>
        )}
        {/* Speaker / embed info */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 4, flexWrap: 'wrap' }}>
          {item.speaker_name && (
            <Text style={{ color: colors.accent, fontSize: 11 }}>{item.speaker_name}</Text>
          )}
          {item.organization && (
            <Text style={{ color: colors.textSecondary, fontSize: 11 }}>{item.organization}</Text>
          )}
          {item.external_link && (
            <a href={item.external_link} target="_blank" rel="noopener noreferrer" style={{ color: colors.textTertiary, fontSize: 11 }}>
              <LinkOutlined /> リンク
            </a>
          )}
          {/* Saved category tags */}
          {hasSaved && item.saved_categories!.map(sc => (
            <Tag
              key={sc.saved_id}
              color={sc.category_color}
              style={{ margin: 0, fontSize: 10, lineHeight: '18px', padding: '0 4px' }}
            >
              {sc.category_name}
            </Tag>
          ))}
        </div>
      </div>

      {/* Right: time + actions */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, minWidth: 80 }}>
        <Tooltip title={publishedTime}>
          <Text style={{ color: colors.textTertiary, fontSize: 11, whiteSpace: 'nowrap' }}>{timeAgo}</Text>
        </Tooltip>
        <Space size={4}>
          {onMarkRead && (
            <Tooltip title={isMarkerHere ? '「ここまで見た」を解除' : 'ここまで見た'}>
              <Button
                type="text"
                size="small"
                icon={isMarkerHere
                  ? <CheckCircleFilled style={{ color: colors.accent }} />
                  : <CheckOutlined />}
                onClick={isMarkerHere ? onClearMark : onMarkRead}
                style={{ color: colors.textSecondary, padding: '0 4px' }}
              />
            </Tooltip>
          )}
          <Tooltip title="保存">
            <Button
              type="text"
              size="small"
              icon={hasSaved ? <StarFilled style={{ color: '#f59e0b' }} /> : <StarOutlined />}
              onClick={onSave}
              style={{ color: colors.textSecondary, padding: '0 4px' }}
            />
          </Tooltip>
          <Tooltip title={item.translation_status === 'done' ? '再翻訳（訳し直す）' : '再翻訳'}>
            <Button
              type="text"
              size="small"
              loading={retranslating}
              icon={<TranslationOutlined />}
              onClick={onRetranslate}
              style={{ color: colors.textSecondary, padding: '0 4px' }}
            />
          </Tooltip>
        </Space>
      </div>
    </div>
  )
}

export default HeadlinesInboxPage
