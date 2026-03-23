import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { Card, Tabs, Spin, Typography, Button, Image, Alert, Breadcrumb } from "antd";
import { ArrowLeftOutlined, PictureOutlined, BarChartOutlined, LineChartOutlined, CalendarOutlined } from "@ant-design/icons";
import axios from "axios";
import TradingViewWidget from "../components/common/TradingViewWidget";

const { Title, Text } = Typography;

type Img = { name: string; url: string };

type ManifestData = {
  symbol: string;
  seasonalityCharts: Img[];
  monthlyReturns: Img[];
  dailyByMonth: Record<string, Img[]>;
};

const MONTHS = [
  { mm: "01", label: "1月" },
  { mm: "02", label: "2月" },
  { mm: "03", label: "3月" },
  { mm: "04", label: "4月" },
  { mm: "05", label: "5月" },
  { mm: "06", label: "6月" },
  { mm: "07", label: "7月" },
  { mm: "08", label: "8月" },
  { mm: "09", label: "9月" },
  { mm: "10", label: "10月" },
  { mm: "11", label: "11月" },
  { mm: "12", label: "12月" },
];

export default function SymbolDetailPage() {
  const { symbol } = useParams();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<ManifestData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeMonth, setActiveMonth] = useState("01");

  const category = params.get("category") || "interest_rates";
  const decodedSymbol = symbol ? decodeURIComponent(symbol) : "";

  useEffect(() => {
    const fetchData = async () => {
      if (!decodedSymbol) return;
      try {
        setLoading(true);
        const response = await axios.get<ManifestData>(
          `/api/seasonality/${encodeURIComponent(decodedSymbol)}/manifest`
        );
        setData(response.data);
        setError(null);
      } catch (err: unknown) {
        console.error("Failed to fetch manifest:", err);
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          setError("指定されたシンボルが見つかりませんでした。");
        } else {
          setError("データの取得に失敗しました。");
        }
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [decodedSymbol]);

  useEffect(() => {
    const m = params.get("month");
    if (m && MONTHS.some((x) => x.mm === m)) {
      setActiveMonth(m);
    }
  }, [params]);

  const onSelectMonth = (mm: string) => {
    setActiveMonth(mm);
    const newParams = new URLSearchParams(params);
    newParams.set("month", mm);
    setParams(newParams, { replace: true });
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: "80px 20px" }}>
        <Spin size="large" />
        <p style={{ marginTop: 16, color: "#666" }}>読み込み中...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: "24px", maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ marginBottom: 24 }}>
          <Link to={`/seasonality?category=${category}`}>
            <Button type="default" icon={<ArrowLeftOutlined />}>
              銘柄一覧へ戻る
            </Button>
          </Link>
        </div>
        <Alert
          message="エラー"
          description={error || "データが見つかりませんでした。"}
          type="error"
          showIcon
        />
      </div>
    );
  }

  const hasMonthlyData = Object.values(data.dailyByMonth).some(
    (imgs) => imgs.length > 0
  );

  const monthTabItems = MONTHS.map((m) => ({
    key: m.mm,
    label: m.label,
    children: (
      <div style={{ marginTop: 16 }}>
        {(data.dailyByMonth[m.mm] || []).map((img) => (
          <ImageCard key={img.url} img={img} />
        ))}
        {(!data.dailyByMonth[m.mm] || data.dailyByMonth[m.mm].length === 0) && (
          <div style={{ textAlign: "center", color: "#999", padding: "60px 20px" }}>
            <PictureOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.5 }} />
            <br />
            <Text type="secondary">この月のデータはありません</Text>
          </div>
        )}
      </div>
    ),
  }));

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      {/* ヘッダー */}
      <div style={{ marginBottom: 32 }}>
        <Breadcrumb
          items={[
            { title: <Link to="/seasonality">シーズナリティ</Link> },
            { title: decodedSymbol },
          ]}
          style={{ marginBottom: 16 }}
        />

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <div>
            <Title level={2} style={{ margin: 0, color: "#1a1a1a" }}>
              {decodedSymbol}
            </Title>
            <Text type="secondary" style={{ fontSize: 15 }}>
              季節性パターン分析
            </Text>
          </div>
          <Link to={`/seasonality?category=${category}`}>
            <Button icon={<ArrowLeftOutlined />} size="large">
              一覧へ戻る
            </Button>
          </Link>
        </div>
      </div>

      {/* シーズナリティ・チャート */}
      <Card
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <LineChartOutlined style={{ color: "#1890ff" }} />
            <span>シーズナリティチャート</span>
          </div>
        }
        style={{ marginBottom: 24, borderRadius: 12 }}
        styles={{ header: { borderBottom: "1px solid #f0f0f0" } }}
      >
        {data.seasonalityCharts.length === 0 ? (
          <div style={{ textAlign: "center", color: "#999", padding: "60px 20px" }}>
            <PictureOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.5 }} />
            <br />
            <Text type="secondary">チャートデータがありません</Text>
          </div>
        ) : (
          <div>
            {data.seasonalityCharts.map((img) => (
              <ImageCard key={img.url} img={img} />
            ))}
          </div>
        )}
      </Card>

      {/* 月別騰落率 */}
      {data.monthlyReturns.length > 0 && (
        <Card
          title={
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <BarChartOutlined style={{ color: "#52c41a" }} />
              <span>月別騰落率</span>
            </div>
          }
          style={{ marginBottom: 24, borderRadius: 12 }}
          styles={{ header: { borderBottom: "1px solid #f0f0f0" } }}
        >
          <div>
            {data.monthlyReturns.map((img) => (
              <ImageCard key={img.url} img={img} />
            ))}
          </div>
        </Card>
      )}

      {/* 日別騰落率 */}
      {hasMonthlyData && (
        <Card
          title={
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <CalendarOutlined style={{ color: "#fa8c16" }} />
              <span>日別騰落率</span>
            </div>
          }
          style={{ marginBottom: 24, borderRadius: 12 }}
          styles={{ header: { borderBottom: "1px solid #f0f0f0" } }}
        >
          <Tabs
            activeKey={activeMonth}
            onChange={onSelectMonth}
            items={monthTabItems}
            type="card"
            size="middle"
            tabBarStyle={{ marginBottom: 0 }}
          />
        </Card>
      )}

      {/* リアルタイムチャート（通貨インデックスは埋め込み不可のため非表示） */}
      {category !== "currency_index" && (
        <Card
          title={
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <LineChartOutlined style={{ color: "#722ed1" }} />
              <span>リアルタイムチャート</span>
            </div>
          }
          style={{ borderRadius: 12 }}
          styles={{ header: { borderBottom: "1px solid #f0f0f0" } }}
        >
          <div style={{ height: 700 }}>
            <TradingViewWidget
              symbol={decodedSymbol}
              height={700}
            />
          </div>
        </Card>
      )}
    </div>
  );
}

function ImageCard({ img }: { img: Img }) {
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
      rootMargin: "50px",
      threshold: 0.1,
    });

    if (cardRef.current) {
      observer.observe(cardRef.current);
    }

    return () => observer.disconnect();
  }, [handleIntersection]);

  return (
    <div ref={cardRef} style={{ marginBottom: 16 }}>
      <div
        style={{
          background: "#fafafa",
          borderRadius: 8,
          overflow: "hidden",
          border: "1px solid #e8e8e8",
          position: "relative",
          minHeight: 200,
        }}
      >
        {isVisible ? (
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
                <Spin />
              </div>
            )}
            <Image
              src={img.url}
              alt={img.name}
              onLoad={() => setImageLoaded(true)}
              style={{
                width: "100%",
                maxHeight: 600,
                objectFit: "contain",
                background: "white",
                opacity: imageLoaded ? 1 : 0,
                transition: "opacity 0.3s ease",
              }}
              preview={{
                mask: (
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    color: "white",
                  }}>
                    <span>クリックで拡大</span>
                  </div>
                ),
              }}
            />
          </>
        ) : (
          <div style={{
            height: 200,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}>
            <Spin />
          </div>
        )}
      </div>
    </div>
  );
}
