import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { Card, Spin, Typography, Button, Image, Alert, Breadcrumb } from "antd";
import { ArrowLeftOutlined, LineChartOutlined, FundOutlined, AppstoreOutlined, FallOutlined, TableOutlined } from "@ant-design/icons";
import axios from "axios";
import TradingViewWidget from "../components/common/TradingViewWidget";
import MonthlyStatsChart from "../components/seasonality/MonthlyStatsChart";
import MonthlyMedianChart from "../components/seasonality/MonthlyMedianChart";
import MonthlyNegRateChart from "../components/seasonality/MonthlyNegRateChart";
import MonthlyStatsTable from "../components/seasonality/MonthlyStatsTable";
import IntramonthPathChart from "../components/seasonality/IntramonthPathChart";
import DailyHeatmapChart from "../components/seasonality/DailyHeatmapChart";

const { Title, Text } = Typography;

// EconAlpha ダークテーマ
const COLORS = {
  bgPrimary: "#0f172a",
  bgSecondary: "#1e293b",
  textPrimary: "#f1f5f9",
  textSecondary: "#94a3b8",
  border: "#334155",
};

type Img = { name: string; url: string };

type ManifestData = {
  symbol: string;
  seasonalityCharts: Img[];
};

export default function SymbolDetailPage() {
  const { symbol } = useParams();
  const [params] = useSearchParams();
  const [data, setData] = useState<ManifestData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: "80px 20px" }}>
        <Spin size="large" />
        <p style={{ marginTop: 16, color: COLORS.textSecondary }}>読み込み中...</p>
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

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      {/* ヘッダー */}
      <div style={{ marginBottom: 32 }}>
        <Breadcrumb
          items={[
            { title: <Link to="/seasonality">シーズナリティ</Link> },
            { title: <span style={{ color: COLORS.textSecondary }}>{decodedSymbol}</span> },
          ]}
          style={{ marginBottom: 16 }}
        />

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <div>
            <Title level={2} style={{ margin: 0, color: COLORS.textPrimary }}>
              {decodedSymbol}
            </Title>
            <Text style={{ fontSize: 15, color: COLORS.textSecondary }}>
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

      {/* シーズナリティ・チャート（EquityClock 画像） */}
      {data.seasonalityCharts.length > 0 && (
        <Card
          title={
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <LineChartOutlined style={{ color: "#1890ff" }} />
              <span style={{ color: COLORS.textPrimary }}>シーズナリティチャート</span>
            </div>
          }
          style={{ marginBottom: 24, borderRadius: 12, background: COLORS.bgPrimary, border: `1px solid ${COLORS.border}` }}
          styles={{
            header: { borderBottom: `1px solid ${COLORS.border}` },
            body: { background: COLORS.bgPrimary },
          }}
        >
          <div>
            {data.seasonalityCharts.map((img) => (
              <ImageCard key={img.url} img={img} />
            ))}
          </div>
        </Card>
      )}

      {/* 平均騰落率（平均バー＋95% CI＋p値） */}
      <Card
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <FundOutlined style={{ color: "#3b82f6" }} />
            <span style={{ color: COLORS.textPrimary }}>平均騰落率</span>
          </div>
        }
        style={{ marginBottom: 24, borderRadius: 12, background: COLORS.bgPrimary, border: `1px solid ${COLORS.border}` }}
        styles={{
          header: { borderBottom: `1px solid ${COLORS.border}` },
          body: { background: COLORS.bgPrimary },
        }}
      >
        <MonthlyStatsChart symbol={decodedSymbol} />
      </Card>

      {/* 月別中央値（外れ値に頑健な代表値） */}
      <Card
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <FundOutlined style={{ color: "#06b6d4" }} />
            <span style={{ color: COLORS.textPrimary }}>月別中央値</span>
          </div>
        }
        style={{ marginBottom: 24, borderRadius: 12, background: COLORS.bgPrimary, border: `1px solid ${COLORS.border}` }}
        styles={{
          header: { borderBottom: `1px solid ${COLORS.border}` },
          body: { background: COLORS.bgPrimary },
        }}
      >
        <MonthlyMedianChart symbol={decodedSymbol} />
      </Card>

      {/* 月別下落率（マイナス年の割合） */}
      <Card
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <FallOutlined style={{ color: "#ef4444" }} />
            <span style={{ color: COLORS.textPrimary }}>月別下落率</span>
          </div>
        }
        style={{ marginBottom: 24, borderRadius: 12, background: COLORS.bgPrimary, border: `1px solid ${COLORS.border}` }}
        styles={{
          header: { borderBottom: `1px solid ${COLORS.border}` },
          body: { background: COLORS.bgPrimary },
        }}
      >
        <MonthlyNegRateChart symbol={decodedSymbol} />
      </Card>

      {/* 月別詳細テーブル（σ・p値・乖離を一覧で比較） */}
      <Card
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <TableOutlined style={{ color: "#8b5cf6" }} />
            <span style={{ color: COLORS.textPrimary }}>月別詳細テーブル</span>
          </div>
        }
        style={{ marginBottom: 24, borderRadius: 12, background: COLORS.bgPrimary, border: `1px solid ${COLORS.border}` }}
        styles={{
          header: { borderBottom: `1px solid ${COLORS.border}` },
          body: { background: COLORS.bgPrimary },
        }}
      >
        <MonthlyStatsTable symbol={decodedSymbol} />
      </Card>

      {/* 月内累積パス（Recharts: 営業日インデックス × 累積平均） */}
      <Card
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <LineChartOutlined style={{ color: "#f59e0b" }} />
            <span style={{ color: COLORS.textPrimary }}>月内累積パス</span>
          </div>
        }
        style={{ marginBottom: 24, borderRadius: 12, background: COLORS.bgPrimary, border: `1px solid ${COLORS.border}` }}
        styles={{
          header: { borderBottom: `1px solid ${COLORS.border}` },
          body: { background: COLORS.bgPrimary },
        }}
      >
        <IntramonthPathChart symbol={decodedSymbol} />
      </Card>

      {/* 日別ヒートマップ（月 × 営業日インデックス） */}
      <Card
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AppstoreOutlined style={{ color: "#10b981" }} />
            <span style={{ color: COLORS.textPrimary }}>日別ヒートマップ</span>
          </div>
        }
        style={{ marginBottom: 24, borderRadius: 12, background: COLORS.bgPrimary, border: `1px solid ${COLORS.border}` }}
        styles={{
          header: { borderBottom: `1px solid ${COLORS.border}` },
          body: { background: COLORS.bgPrimary },
        }}
      >
        <DailyHeatmapChart symbol={decodedSymbol} />
      </Card>

      {/* リアルタイムチャート（通貨インデックスは埋め込み不可のため非表示） */}
      {category !== "currency_index" && (
        <Card
          title={
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <LineChartOutlined style={{ color: "#722ed1" }} />
              <span style={{ color: COLORS.textPrimary }}>リアルタイムチャート</span>
            </div>
          }
          style={{ borderRadius: 12, background: COLORS.bgPrimary, border: `1px solid ${COLORS.border}` }}
          styles={{
            header: { borderBottom: `1px solid ${COLORS.border}` },
            body: { background: COLORS.bgPrimary },
          }}
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
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
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
              wrapperStyle={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "100%",
              }}
              style={{
                maxWidth: "100%",
                maxHeight: 600,
                width: "auto",
                height: "auto",
                objectFit: "contain",
                background: "white",
                display: "block",
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
