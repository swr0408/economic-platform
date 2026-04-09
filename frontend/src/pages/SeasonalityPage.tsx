import { useEffect, useState, useRef, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Tabs, Typography, Spin, Alert, Badge, Tooltip } from "antd";
import type { TabsProps } from "antd";
import { QuestionCircleOutlined, BarChartOutlined } from "@ant-design/icons";
import axios from "axios";
import { useHandbook } from "../contexts/HandbookContext";

const { Title, Text } = Typography;

// EconAlpha カラーパレット
const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  bgTertiary: '#334155',
  accent: '#10b981',
  accentHover: '#34d399',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textTertiary: '#64748b',
  border: '#334155',
  info: '#3b82f6',
};

type Item = {
  symbol: string;
  coverUrl?: string;
};

type Subcategory = {
  name: string;
  items: Item[];
};

type Category = {
  name: string;
  items: Item[];
  subcategories: Record<string, Subcategory>;
};

type IndexData = {
  categories: Record<string, Category>;
};

export default function SeasonalityPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { openHandbook } = useHandbook();
  const [data, setData] = useState<IndexData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const activeCategory = searchParams.get("category") || "interest_rates";

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await axios.get<IndexData>("/api/seasonality/index");
        setData(response.data);
        setError(null);
      } catch (err) {
        console.error("Failed to fetch seasonality index:", err);
        setError("データの取得に失敗しました。バックエンドサーバーが起動しているか確認してください。");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleCategoryChange = (key: string) => {
    setSearchParams({ category: key });
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: "80px 20px" }}>
        <Spin size="large" />
        <p style={{ marginTop: 16, color: colors.textSecondary }}>読み込み中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "24px" }}>
        <Alert message="エラー" description={error} type="error" showIcon />
      </div>
    );
  }

  if (!data || !data.categories) {
    return (
      <div style={{ padding: "24px" }}>
        <Alert message="データなし" description="シーズナリティデータがありません。" type="warning" showIcon />
      </div>
    );
  }

  const categories = data.categories;

  const tabItems: TabsProps["items"] = Object.entries(categories)
    .map(([catId, cat]) => {
      const totalItems =
        cat.items.length +
        Object.values(cat.subcategories || {}).reduce((sum, sub) => sum + sub.items.length, 0);

      if (totalItems === 0) return null;

      return {
        key: catId,
        label: (
          <span style={{ padding: "0 4px" }}>
            {cat.name}
            <Badge
              count={totalItems}
              style={{
                marginLeft: 8,
                backgroundColor: catId === activeCategory ? colors.accent : colors.bgTertiary,
                fontSize: 11
              }}
            />
          </span>
        ),
        children: (
          <div style={{ paddingTop: 8 }}>
            {cat.items.length > 0 && (
              <div style={{ marginBottom: 32 }}>
                <div className="asset-grid">
                  {cat.items.map((item) => (
                    <SymbolCard key={item.symbol} item={item} activeCategory={catId} />
                  ))}
                </div>
              </div>
            )}

            {Object.entries(cat.subcategories || {}).map(([subId, subcategory]) => {
              if (subcategory.items.length === 0) return null;

              return (
                <div key={subId} style={{ marginBottom: 32 }}>
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    marginBottom: 16,
                    paddingBottom: 10,
                    borderBottom: `1px solid ${colors.border}`
                  }}>
                    <Title level={5} style={{ margin: 0, color: colors.textPrimary }}>
                      {subcategory.name}
                    </Title>
                    <Badge
                      count={subcategory.items.length}
                      style={{ marginLeft: 12, backgroundColor: colors.accent }}
                    />
                  </div>
                  <div className="asset-grid">
                    {subcategory.items.map((item) => (
                      <SymbolCard key={item.symbol} item={item} activeCategory={catId} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ),
      };
    })
    .filter((item): item is NonNullable<typeof item> => item !== null);

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto", padding: "4px 8px" }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
            シーズナリティ分析
          </Title>
          <Tooltip title="アノマリー活用ガイド - データハンドブック">
            <QuestionCircleOutlined
              onClick={() => openHandbook('anomaly-guide')}
              style={{ fontSize: 18, color: colors.textSecondary, cursor: 'pointer', transition: 'color 0.2s' }}
              onMouseEnter={(e) => { (e.target as HTMLElement).style.color = '#10b981' }}
              onMouseLeave={(e) => { (e.target as HTMLElement).style.color = colors.textSecondary }}
            />
          </Tooltip>
          <Tooltip title="リバランス（月末・四半期末・半期末） - データハンドブック">
            <QuestionCircleOutlined
              onClick={() => openHandbook('rebalance')}
              style={{ fontSize: 18, color: colors.textSecondary, cursor: 'pointer', transition: 'color 0.2s' }}
              onMouseEnter={(e) => { (e.target as HTMLElement).style.color = '#10b981' }}
              onMouseLeave={(e) => { (e.target as HTMLElement).style.color = colors.textSecondary }}
            />
          </Tooltip>
          <Tooltip title="フロー（資金フロー・市場のクセ） - データハンドブック">
            <QuestionCircleOutlined
              onClick={() => openHandbook('flow-knowledge')}
              style={{ fontSize: 18, color: colors.textSecondary, cursor: 'pointer', transition: 'color 0.2s' }}
              onMouseEnter={(e) => { (e.target as HTMLElement).style.color = '#10b981' }}
              onMouseLeave={(e) => { (e.target as HTMLElement).style.color = colors.textSecondary }}
            />
          </Tooltip>
        </div>
        <Text style={{ fontSize: 13, color: colors.textSecondary }}>
          アセット別の季節性パターンを確認できます
        </Text>
      </div>

      <Tabs
        activeKey={activeCategory}
        onChange={handleCategoryChange}
        items={tabItems}
        size="middle"
        tabBarStyle={{
          marginBottom: 20,
          borderBottom: `1px solid ${colors.border}`,
        }}
      />
    </div>
  );
}

function SymbolCard({ item, activeCategory }: { item: Item; activeCategory: string }) {
  const [isVisible, setIsVisible] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  const handleIntersection = useCallback((entries: IntersectionObserverEntry[]) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        setIsVisible(true);
      }
    });
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(handleIntersection, {
      rootMargin: "100px",
      threshold: 0.1,
    });

    if (cardRef.current) {
      observer.observe(cardRef.current);
    }

    return () => observer.disconnect();
  }, [handleIntersection]);

  return (
    <div ref={cardRef}>
      <Link
        to={`/seasonality/${encodeURIComponent(item.symbol)}?category=${activeCategory}`}
        style={{ textDecoration: "none" }}
      >
        <div
          style={{
            background: colors.bgSecondary,
            borderRadius: 10,
            overflow: "hidden",
            boxShadow: "0 2px 12px rgba(0,0,0,0.2)",
            transition: "all 0.2s ease",
            cursor: "pointer",
            border: `1px solid ${colors.border}`,
          }}
          className="symbol-card"
        >
          {/* 画像エリア */}
          <div
            style={{
              height: 160,
              overflow: "hidden",
              background: colors.bgTertiary,
              position: "relative",
            }}
          >
            {isVisible && item.coverUrl ? (
              <>
                {!imageLoaded && (
                  <div style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: colors.bgTertiary,
                  }}>
                    <Spin size="small" />
                  </div>
                )}
                <img
                  src={item.coverUrl}
                  alt={item.symbol}
                  loading="lazy"
                  onLoad={() => setImageLoaded(true)}
                  style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    opacity: imageLoaded ? 1 : 0,
                    transition: "opacity 0.3s ease",
                  }}
                />
              </>
            ) : (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                  color: colors.textSecondary,
                  gap: 8,
                }}
              >
                <BarChartOutlined style={{ fontSize: 28, color: colors.accent }} />
                <span style={{ fontSize: 12 }}>統計データのみ</span>
              </div>
            )}
          </div>

          {/* 情報エリア */}
          <div style={{ padding: "12px 14px" }}>
            <div
              style={{
                fontWeight: 600,
                fontSize: 14,
                color: colors.textPrimary,
                marginBottom: 6,
              }}
            >
              {item.symbol}
            </div>

          </div>
        </div>
      </Link>
    </div>
  );
}
