/**
 * 比較指標選択ポップオーバー
 * 国 > カテゴリ > 指標 の階層表示 + 検索
 * 市場タブを国タブと並列に配置
 */

import { useState, useMemo, useEffect } from 'react';
import { Popover, Input, Tabs, List, Tag, Typography, Space, Button, Collapse } from 'antd';
import { SearchOutlined, PlusOutlined, LineChartOutlined } from '@ant-design/icons';
import { DARK_THEME } from '../country/usa/common/chartConstants';
import {
  INDICATOR_CATEGORIES,
  INDICATOR_COUNTRIES,
  INDICATOR_SUB_CATEGORIES,
  getEconomicIndicatorsByCountry,
  getIndicatorsBySubCategory,
  getMarketIndicators,
  getMarketIndicatorsBySubCategory,
  getFrequencyLabel,
  searchIndicators,
  type OverlayIndicator,
} from '../../constants/overlayConfig';

const { Text } = Typography;
const { TabPane } = Tabs;
const { Panel } = Collapse;

// 市場カテゴリ定義（第2レベルタブ）
const MARKET_CATEGORIES = {
  all: '全て',
  bond: '債券利回り',
  index: '株価指数',
  commodity: '商品',
  forex: '為替',
} as const;

// 市場カテゴリ配下のサブカテゴリマッピング
const MARKET_CATEGORY_SUB_CATEGORIES: Record<string, string[]> = {
  bond: ['bond'],
  index: ['index_us', 'index_asia', 'index_europe', 'calculated_index'],
  commodity: ['commodity_metal', 'commodity_energy', 'calculated_commodity'],
  forex: ['forex_usd', 'forex_jpy', 'forex_cross', 'forex_index'],
};

// 市場サブカテゴリのラベル
const MARKET_SUB_CATEGORY_LABELS: Record<string, string> = {
  forex_usd: 'ドルストレート',
  forex_jpy: 'クロス円',
  forex_cross: 'その他クロス',
  forex_index: '通貨インデックス',
  index_us: '米国株価指数',
  index_asia: '日本・アジア',
  index_europe: '欧州',
  bond: '債券利回り',
  commodity_metal: '貴金属',
  commodity_energy: 'エネルギー',
  calculated_index: 'ドル建て日経平均',
  calculated_commodity: '計算値',
};

// =============================================================================
// Props
// =============================================================================

export interface ComparePopoverProps {
  /** 選択中の比較指標ID一覧 */
  selectedIndicatorIds: string[];
  /** メイン指標ID */
  mainIndicatorId: string;
  /** 指標選択時のハンドラ */
  onSelect: (indicator: OverlayIndicator) => void;
  /** 最大選択数 */
  maxSelections?: number;
  /** ボタンラベル */
  buttonText?: string;
  /** 無効化 */
  disabled?: boolean;
}

// =============================================================================
// 指標アイテム
// =============================================================================

interface IndicatorItemProps {
  indicator: OverlayIndicator;
  isSelected: boolean;
  isMain: boolean;
  onSelect: () => void;
}

function IndicatorItem({ indicator, isSelected, isMain, onSelect }: IndicatorItemProps) {
  const isDisabled = isSelected || isMain;

  return (
    <List.Item
      style={{
        padding: '8px 12px',
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        backgroundColor: isDisabled ? DARK_THEME.bgTertiary : 'transparent',
        opacity: isDisabled ? 0.6 : 1,
      }}
      onClick={() => !isDisabled && onSelect()}
    >
      <Space direction="vertical" size={0} style={{ width: '100%' }}>
        <Space>
          <Text strong={!isDisabled} style={{ fontSize: 13, color: DARK_THEME.textPrimary }}>
            {indicator.name}
          </Text>
          {isSelected && (
            <Tag color="blue" style={{ fontSize: 10, padding: '0 4px' }}>
              選択中
            </Tag>
          )}
          {isMain && (
            <Tag color="gold" style={{ fontSize: 10, padding: '0 4px' }}>
              メイン
            </Tag>
          )}
        </Space>
        <Space size={4}>
          <Tag
            style={{
              fontSize: 10,
              padding: '0 4px',
              margin: 0,
              backgroundColor: DARK_THEME.bgSecondary,
              border: `1px solid ${DARK_THEME.borderLight}`,
              color: DARK_THEME.textSecondary,
            }}
          >
            {getFrequencyLabel(indicator.frequency)}
          </Tag>
          <Text style={{ fontSize: 11, color: DARK_THEME.textTertiary }}>
            {indicator.nameEn}
          </Text>
        </Space>
      </Space>
    </List.Item>
  );
}

// =============================================================================
// 比較指標選択
// =============================================================================

export function ComparePopover({
  selectedIndicatorIds,
  mainIndicatorId,
  onSelect,
  maxSelections = 3,
  buttonText = '比較指標を追加',
  disabled = false,
}: ComparePopoverProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTopTab, setActiveTopTab] = useState<string>('usa');
  const [activeCategory, setActiveCategory] = useState<string>('all');

  // 検索結果
  const filteredIndicators = useMemo(() => {
    if (!searchQuery.trim()) {
      return null;
    }
    return searchIndicators(searchQuery);
  }, [searchQuery]);

  // 経済指標を国別にグループ化（市場データを除く）
  const indicatorsByCountry = useMemo(() => getEconomicIndicatorsByCountry(), []);
  const countryEntries = useMemo(
    () => Object.entries(indicatorsByCountry).filter(([, indicators]) => indicators.length > 0),
    [indicatorsByCountry]
  );

  // 市場データをサブカテゴリ別にグループ化
  const marketBySubCategory = useMemo(() => getMarketIndicatorsBySubCategory(), []);

  useEffect(() => {
    // 初期タブの設定
    if (activeTopTab !== 'market' && countryEntries.length > 0) {
      if (!countryEntries.some(([key]) => key === activeTopTab)) {
        setActiveTopTab(countryEntries[0][0]);
        setActiveCategory('all');
      }
    }
  }, [countryEntries, activeTopTab]);

  const canAddMore = selectedIndicatorIds.length < maxSelections;

  const handleSelect = (indicator: OverlayIndicator) => {
    onSelect(indicator);
    setOpen(false);
    setSearchQuery('');
  };

  const content = (
    <div style={{ width: 320, backgroundColor: DARK_THEME.bgSecondary, color: DARK_THEME.textPrimary }}>
      {/* 検索 */}
      <Input
        placeholder="指標を検索..."
        prefix={<SearchOutlined style={{ color: DARK_THEME.textTertiary }} />}
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        style={{
          marginBottom: 12,
          backgroundColor: DARK_THEME.bgTertiary,
          borderColor: DARK_THEME.borderLight,
          color: DARK_THEME.textPrimary,
        }}
        allowClear
      />

      {/* 選択数 */}
      <div style={{ marginBottom: 8 }}>
        <Text style={{ fontSize: 11, color: DARK_THEME.textSecondary }}>
          {selectedIndicatorIds.length} / {maxSelections} 選択中
        </Text>
        {!canAddMore && (
          <Text style={{ fontSize: 11, marginLeft: 8, color: '#faad14' }}>
            これ以上追加できません
          </Text>
        )}
      </div>

      {/* リスト */}
      {filteredIndicators ? (
        <div style={{ maxHeight: 300, overflowY: 'auto' }}>
          {filteredIndicators.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center' }}>
              <Text style={{ color: DARK_THEME.textSecondary }}>該当する指標がありません</Text>
            </div>
          ) : (
            <List
              size="small"
              dataSource={filteredIndicators}
              renderItem={(indicator) => (
                <IndicatorItem
                  indicator={indicator}
                  isSelected={selectedIndicatorIds.includes(indicator.id)}
                  isMain={indicator.id === mainIndicatorId}
                  onSelect={() => handleSelect(indicator)}
                />
              )}
            />
          )}
        </div>
      ) : (
        <Tabs
          activeKey={activeTopTab}
          onChange={(key) => {
            setActiveTopTab(key);
            setActiveCategory('all');
          }}
          size="small"
          style={{ marginTop: -8 }}
        >
          {/* 国別タブ（経済指標） */}
          {countryEntries.map(([countryKey, indicators]) => {
            const countryLabel =
              INDICATOR_COUNTRIES[countryKey as keyof typeof INDICATOR_COUNTRIES] || countryKey;

            return (
              <TabPane tab={countryLabel} key={countryKey}>
                <Tabs
                  activeKey={activeCategory}
                  onChange={setActiveCategory}
                  size="small"
                  style={{ marginTop: -8 }}
                >
                  <TabPane tab="全て" key="all">
                    <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                      <List
                        size="small"
                        dataSource={indicators}
                        renderItem={(indicator) => (
                          <IndicatorItem
                            indicator={indicator}
                            isSelected={selectedIndicatorIds.includes(indicator.id)}
                            isMain={indicator.id === mainIndicatorId}
                            onSelect={() => handleSelect(indicator)}
                          />
                        )}
                      />
                    </div>
                  </TabPane>

                  {Object.entries(INDICATOR_CATEGORIES)
                    .filter(([key]) => key !== 'market') // 市場カテゴリを除外
                    .map(([categoryKey, categoryLabel]) => {
                      const subCategoryGroups = getIndicatorsBySubCategory(
                        categoryKey,
                        countryKey as keyof typeof INDICATOR_COUNTRIES
                      );
                      const subCategoryKeys = Object.keys(subCategoryGroups);
                      if (subCategoryKeys.length === 0) return null;

                      return (
                        <TabPane tab={categoryLabel} key={categoryKey}>
                          <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                            <Collapse
                              defaultActiveKey={subCategoryKeys}
                              ghost
                              size="small"
                              style={{ backgroundColor: 'transparent' }}
                            >
                              {subCategoryKeys.map((subKey) => {
                                const subIndicators = subCategoryGroups[subKey];
                                const subLabel =
                                  INDICATOR_SUB_CATEGORIES[subKey as keyof typeof INDICATOR_SUB_CATEGORIES] ||
                                  subKey;

                                return (
                                  <Panel
                                    header={
                                      <Text strong style={{ fontSize: 12 }}>
                                        {subLabel}
                                        <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>
                                          ({subIndicators.length})
                                        </Text>
                                      </Text>
                                    }
                                    key={subKey}
                                    style={{ padding: 0 }}
                                  >
                                    <List
                                      size="small"
                                      dataSource={subIndicators}
                                      renderItem={(indicator) => (
                                        <IndicatorItem
                                          indicator={indicator}
                                          isSelected={selectedIndicatorIds.includes(indicator.id)}
                                          isMain={indicator.id === mainIndicatorId}
                                          onSelect={() => handleSelect(indicator)}
                                        />
                                      )}
                                    />
                                  </Panel>
                                );
                              })}
                            </Collapse>
                          </div>
                        </TabPane>
                      );
                    })}
                </Tabs>
              </TabPane>
            );
          })}

          {/* 市場タブ */}
          <TabPane tab="市場" key="market">
            <Tabs
              activeKey={activeCategory}
              onChange={setActiveCategory}
              size="small"
              style={{ marginTop: -8 }}
            >
              {/* 全て */}
              <TabPane tab={MARKET_CATEGORIES.all} key="all">
                <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                  <List
                    size="small"
                    dataSource={getMarketIndicators()}
                    renderItem={(indicator) => (
                      <IndicatorItem
                        indicator={indicator}
                        isSelected={selectedIndicatorIds.includes(indicator.id)}
                        isMain={indicator.id === mainIndicatorId}
                        onSelect={() => handleSelect(indicator)}
                      />
                    )}
                  />
                </div>
              </TabPane>

              {/* 債券利回り、株価指数、商品、為替 */}
              {Object.entries(MARKET_CATEGORIES)
                .filter(([key]) => key !== 'all')
                .map(([categoryKey, categoryLabel]) => {
                  const subCategoryKeys = MARKET_CATEGORY_SUB_CATEGORIES[categoryKey] || [];
                  const subCategoryGroups: Record<string, typeof marketBySubCategory[string]> = {};

                  // このカテゴリに属するサブカテゴリをフィルタリング
                  for (const subKey of subCategoryKeys) {
                    if (marketBySubCategory[subKey]) {
                      subCategoryGroups[subKey] = marketBySubCategory[subKey];
                    }
                  }

                  const hasData = Object.keys(subCategoryGroups).length > 0;
                  if (!hasData) return null;

                  return (
                    <TabPane tab={categoryLabel} key={categoryKey}>
                      <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                        <Collapse
                          defaultActiveKey={subCategoryKeys.slice(0, 3)}
                          ghost
                          size="small"
                          style={{ backgroundColor: 'transparent' }}
                        >
                          {Object.keys(subCategoryGroups).map((subKey) => {
                            const indicators = subCategoryGroups[subKey];
                            const subLabel = MARKET_SUB_CATEGORY_LABELS[subKey] || subKey;

                            return (
                              <Panel
                                header={
                                  <Text strong style={{ fontSize: 12 }}>
                                    {subLabel}
                                    <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>
                                      ({indicators.length})
                                    </Text>
                                  </Text>
                                }
                                key={subKey}
                                style={{ padding: 0 }}
                              >
                                <List
                                  size="small"
                                  dataSource={indicators}
                                  renderItem={(indicator) => (
                                    <IndicatorItem
                                      indicator={indicator}
                                      isSelected={selectedIndicatorIds.includes(indicator.id)}
                                      isMain={indicator.id === mainIndicatorId}
                                      onSelect={() => handleSelect(indicator)}
                                    />
                                  )}
                                />
                              </Panel>
                            );
                          })}
                        </Collapse>
                      </div>
                    </TabPane>
                  );
                })}
            </Tabs>
          </TabPane>
        </Tabs>
      )}
    </div>
  );

  return (
    <Popover
      content={content}
      title={
        <Space style={{ color: DARK_THEME.textPrimary }}>
          <LineChartOutlined />
          <span>比較する指標を選択</span>
        </Space>
      }
      trigger="click"
      open={open}
      onOpenChange={(visible) => {
        if (!disabled && canAddMore) {
          setOpen(visible);
          if (!visible) {
            setSearchQuery('');
          }
        }
      }}
      placement="bottomLeft"
      overlayStyle={{
        backgroundColor: DARK_THEME.bgSecondary,
      }}
      overlayInnerStyle={{
        backgroundColor: DARK_THEME.bgSecondary,
        border: `1px solid ${DARK_THEME.borderLight}`,
      }}
    >
      <Button
        type="dashed"
        icon={<PlusOutlined />}
        size="small"
        disabled={disabled || !canAddMore}
        style={{
          borderColor: canAddMore ? DARK_THEME.accent : DARK_THEME.borderLight,
          color: canAddMore ? DARK_THEME.accent : DARK_THEME.textTertiary,
          backgroundColor: 'transparent',
        }}
      >
        {buttonText}
      </Button>
    </Popover>
  );
}

export default ComparePopover;
