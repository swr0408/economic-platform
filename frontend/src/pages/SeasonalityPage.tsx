import { useEffect, useState, useRef, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Tabs, Typography, Spin, Alert, Badge } from "antd";
import type { TabsProps } from "antd";
import axios from "axios";

const { Title, Text } = Typography;

type Item = {
  symbol: string;
  coverUrl?: string;
  counts?: {
    seasonality: number;
    monthly: number;
    daily: number;
  };
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
        <p style={{ marginTop: 16, color: "#666" }}>読み込み中...</p>
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
                backgroundColor: catId === activeCategory ? "#1890ff" : "#d9d9d9",
                fontSize: 11
              }}
            />
          </span>
        ),
        children: (
          <div style={{ paddingTop: 8 }}>
            {cat.items.length > 0 && (
              <div style={{ marginBottom: 40 }}>
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
                <div key={subId} style={{ marginBottom: 40 }}>
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    marginBottom: 20,
                    paddingBottom: 12,
                    borderBottom: "2px solid #f0f0f0"
                  }}>
                    <Title level={4} style={{ margin: 0, color: "#1a1a1a" }}>
                      {subcategory.name}
                    </Title>
                    <Badge
                      count={subcategory.items.length}
                      style={{ marginLeft: 12, backgroundColor: "#52c41a" }}
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
    <div style={{ maxWidth: 1400, margin: "0 auto" }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2} style={{ marginBottom: 8, color: "#1a1a1a" }}>
          シーズナリティ分析
        </Title>
        <Text type="secondary" style={{ fontSize: 15 }}>
          アセット別の季節性パターンを確認できます
        </Text>
      </div>

      <Tabs
        activeKey={activeCategory}
        onChange={handleCategoryChange}
        items={tabItems}
        size="large"
        tabBarStyle={{
          marginBottom: 24,
          borderBottom: "1px solid #e8e8e8",
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
            background: "#fff",
            borderRadius: 12,
            overflow: "hidden",
            boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
            transition: "all 0.3s ease",
            cursor: "pointer",
            border: "1px solid #e8e8e8",
          }}
          className="symbol-card"
        >
          {/* 画像エリア */}
          <div
            style={{
              height: 180,
              overflow: "hidden",
              background: "#fafafa",
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
                    background: "#f5f5f5",
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
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                  color: "#bbb",
                  fontSize: 14,
                }}
              >
                {isVisible ? "No Image" : ""}
              </div>
            )}
          </div>

          {/* 情報エリア */}
          <div style={{ padding: "16px" }}>
            <div
              style={{
                fontWeight: 600,
                fontSize: 16,
                color: "#1a1a1a",
                marginBottom: 8,
              }}
            >
              {item.symbol}
            </div>

            {item.counts && (
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <Text type="secondary" style={{ fontSize: 13 }}>
                  シーズナリティ: <span style={{ color: "#1890ff", fontWeight: 500 }}>{item.counts.seasonality}</span>
                </Text>
                <Text type="secondary" style={{ fontSize: 13 }}>
                  月次: <span style={{ color: "#1890ff", fontWeight: 500 }}>{item.counts.monthly}</span>
                </Text>
                <Text type="secondary" style={{ fontSize: 13 }}>
                  日次: <span style={{ color: "#52c41a", fontWeight: 500 }}>{item.counts.daily}</span>
                </Text>
              </div>
            )}
          </div>
        </div>
      </Link>
    </div>
  );
}
