import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Spin, Alert, Segmented, Tag, Tooltip, Collapse, Typography, Empty } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined, FireOutlined } from "@ant-design/icons";
import axios from "axios";

const { Text, Title } = Typography;

// EconAlpha カラーパレット（SeasonalityPage と統一）
const colors = {
  bgPrimary: "#0f172a",
  bgSecondary: "#1e293b",
  bgTertiary: "#334155",
  accent: "#10b981",
  accentHover: "#34d399",
  textPrimary: "#f1f5f9",
  textSecondary: "#94a3b8",
  textTertiary: "#64748b",
  border: "#334155",
  bullish: "#10b981",
  bearish: "#ef4444",
  both: "#f59e0b",
};

type Period = "full" | "recent" | "both";
type Direction = "bullish" | "bearish";
type Chart = "mean" | "median" | "neg_rate" | "table" | "intramonth" | "daily";

type Event = {
  symbol: string;
  month: number;
  period: Period;
  chart: Chart;
  direction: Direction;
  metric: Record<string, any>;
};

type AnalysisData = {
  generated_at: string;
  periods: { full: string; recent: string };
  thresholds: Record<string, number>;
  symbols: string[];
  events: Event[];
};

const CHART_LABEL: Record<Chart, string> = {
  mean: "平均",
  median: "中央値",
  neg_rate: "下落率",
  table: "テーブル(複合)",
  intramonth: "月内パス",
  daily: "日別",
};

const CHART_DESCRIPTION: Record<Chart, string> = {
  mean: "月別平均騰落率が±1.0%以上 かつ p<0.05",
  median: "月別中央値が±1.0%以上",
  neg_rate: "下落率が20%以下（高勝率）または80%以上（高負け率）",
  table: "平均・中央値・下落率の3指標が全て同方向で閾値を満たす最強シグナル",
  intramonth: "月内累積平均パスの月末値が±1.0%以上",
  daily: "月内のある1営業日で平均が±0.5%以上 (n≥10)",
};

const PERIOD_LABEL: Record<Period, string> = {
  full: "長期",
  recent: "直近",
  both: "長期＋直近一致",
};

const MONTH_NAMES = [
  "1月", "2月", "3月", "4月", "5月", "6月",
  "7月", "8月", "9月", "10月", "11月", "12月",
];

function fmtMetric(e: Event): string {
  const m = e.metric;
  switch (e.chart) {
    case "mean":
      return `mean ${(m.mean >= 0 ? "+" : "")}${m.mean.toFixed(2)}%, p=${m.p_value.toFixed(3)}, n=${m.n}`;
    case "median":
      return `median ${(m.median >= 0 ? "+" : "")}${m.median.toFixed(2)}%, n=${m.n}`;
    case "neg_rate":
      return `neg=${(m.neg_rate * 100).toFixed(0)}%, n=${m.n}`;
    case "table":
      return `mean ${(m.mean >= 0 ? "+" : "")}${m.mean.toFixed(2)}%, median ${(m.median >= 0 ? "+" : "")}${m.median.toFixed(2)}%, neg=${(m.neg_rate * 100).toFixed(0)}%, p=${m.p_value.toFixed(3)}`;
    case "intramonth":
      return `月末累積 ${(m.cum_end >= 0 ? "+" : "")}${m.cum_end.toFixed(2)}%`;
    case "daily":
      return `第${m.day}営業日 mean ${(m.mean_pct >= 0 ? "+" : "")}${m.mean_pct.toFixed(2)}%, n=${m.n}`;
  }
}

function fmtMetricBoth(e: Event): string {
  // period=both のとき metric には full/recent ネストが入る
  if (!e.metric.full || !e.metric.recent) return fmtMetric(e);
  const fakeFull: Event = { ...e, period: "full", metric: e.metric.full };
  const fakeRecent: Event = { ...e, period: "recent", metric: e.metric.recent };
  return `Full: ${fmtMetric(fakeFull)} / 直近: ${fmtMetric(fakeRecent)}`;
}

function dirColor(d: Direction): string {
  return d === "bullish" ? colors.bullish : colors.bearish;
}

function dirIcon(d: Direction) {
  return d === "bullish" ? <ArrowUpOutlined /> : <ArrowDownOutlined />;
}

function periodColor(p: Period): string {
  if (p === "both") return colors.both;
  if (p === "full") return "#3b82f6";
  return "#8b5cf6";
}

export default function AnalysisListView() {
  const [data, setData] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [viewMode, setViewMode] = useState<"month" | "symbol" | "chart">("month");
  const [periodFilter, setPeriodFilter] = useState<"all" | Period>("both");
  const [directionFilter, setDirectionFilter] = useState<"all" | Direction>("all");
  const [chartFilter, setChartFilter] = useState<"all" | Chart>("all");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        setLoading(true);
        const r = await axios.get<AnalysisData>("/api/seasonality/analysis");
        if (!alive) return;
        setData(r.data);
        setError(null);
      } catch (e: any) {
        if (!alive) return;
        console.error("Failed to fetch analysis:", e);
        setError("分析データの取得に失敗しました");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const filtered = useMemo<Event[]>(() => {
    if (!data) return [];
    return data.events.filter(e => {
      if (periodFilter !== "all" && e.period !== periodFilter) return false;
      if (directionFilter !== "all" && e.direction !== directionFilter) return false;
      if (chartFilter !== "all" && e.chart !== chartFilter) return false;
      return true;
    });
  }, [data, periodFilter, directionFilter, chartFilter]);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: "60px 20px" }}>
        <Spin size="large" />
        <p style={{ marginTop: 16, color: colors.textSecondary }}>分析データを読み込み中...</p>
      </div>
    );
  }
  if (error) {
    return <Alert message="エラー" description={error} type="error" showIcon />;
  }
  if (!data) {
    return <Alert message="データなし" type="warning" showIcon />;
  }

  return (
    <div>
      {/* ヘッダー & 閾値説明 */}
      <div style={{
        background: colors.bgSecondary,
        border: `1px solid ${colors.border}`,
        borderRadius: 8,
        padding: "12px 16px",
        marginBottom: 16,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <FireOutlined style={{ color: colors.accent }} />
          <Text style={{ color: colors.textPrimary, fontSize: 14, fontWeight: 600 }}>
            シーズナリティ・シグナル分析
          </Text>
          <Tag color={colors.both} style={{ marginLeft: 8 }}>
            長期＋直近一致 {data.events.filter(e => e.period === "both").length}件
          </Tag>
          <Tag color="default">
            全シグナル {data.events.length.toLocaleString()}件
          </Tag>
        </div>
        <Text style={{ color: colors.textSecondary, fontSize: 12 }}>
          長期={data.periods.full} / 直近={data.periods.recent} ・ 推奨デフォルト閾値で抽出
          ・ 「長期＋直近一致」は両期間で同じ傾向が確認できたシグナル
        </Text>
      </div>

      {/* フィルタ */}
      <div style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 16,
        marginBottom: 16,
        padding: "10px 14px",
        background: colors.bgSecondary,
        border: `1px solid ${colors.border}`,
        borderRadius: 8,
      }}>
        <FilterRow label="ビュー">
          <Segmented
            value={viewMode}
            onChange={(v) => setViewMode(v as any)}
            options={[
              { label: "月別", value: "month" },
              { label: "銘柄別", value: "symbol" },
              { label: "チャート種別", value: "chart" },
            ]}
          />
        </FilterRow>
        <FilterRow label="期間">
          <Segmented
            value={periodFilter}
            onChange={(v) => setPeriodFilter(v as any)}
            options={[
              { label: "長期＋直近一致", value: "both" },
              { label: "長期", value: "full" },
              { label: "直近", value: "recent" },
              { label: "全て", value: "all" },
            ]}
          />
        </FilterRow>
        <FilterRow label="方向">
          <Segmented
            value={directionFilter}
            onChange={(v) => setDirectionFilter(v as any)}
            options={[
              { label: "全て", value: "all" },
              { label: "強気↑", value: "bullish" },
              { label: "弱気↓", value: "bearish" },
            ]}
          />
        </FilterRow>
        <FilterRow label="チャート">
          <Segmented
            value={chartFilter}
            onChange={(v) => setChartFilter(v as any)}
            options={[
              { label: "全て", value: "all" },
              { label: CHART_LABEL.mean, value: "mean" },
              { label: CHART_LABEL.median, value: "median" },
              { label: CHART_LABEL.neg_rate, value: "neg_rate" },
              { label: CHART_LABEL.table, value: "table" },
              { label: CHART_LABEL.intramonth, value: "intramonth" },
              { label: CHART_LABEL.daily, value: "daily" },
            ]}
          />
        </FilterRow>
      </div>

      <Text style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 12, display: "block" }}>
        絞り込み後: <b style={{ color: colors.textPrimary }}>{filtered.length.toLocaleString()}</b> 件
      </Text>

      {filtered.length === 0 && (
        <Empty description={<span style={{ color: colors.textSecondary }}>該当するシグナルはありません</span>} />
      )}

      {filtered.length > 0 && viewMode === "month" && <MonthView events={filtered} />}
      {filtered.length > 0 && viewMode === "symbol" && <SymbolView events={filtered} />}
      {filtered.length > 0 && viewMode === "chart" && <ChartView events={filtered} />}
    </div>
  );
}

function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <Text style={{ color: colors.textSecondary, fontSize: 12, minWidth: 50 }}>{label}:</Text>
      {children}
    </div>
  );
}

// ──────────── 月別ビュー ────────────
function MonthView({ events }: { events: Event[] }) {
  // 月→[events]
  const byMonth = useMemo(() => {
    const m: Record<number, Event[]> = {};
    for (const e of events) {
      (m[e.month] ||= []).push(e);
    }
    return m;
  }, [events]);

  const items = useMemo(() => {
    return Array.from({ length: 12 }, (_, i) => i + 1)
      .filter(mo => (byMonth[mo] || []).length > 0)
      .map(mo => {
        const arr = byMonth[mo];
        const bull = arr.filter(e => e.direction === "bullish");
        const bear = arr.filter(e => e.direction === "bearish");
        return {
          key: String(mo),
          label: (
            <span>
              <b style={{ color: colors.textPrimary }}>{MONTH_NAMES[mo - 1]}</b>
              <Tag color={colors.bullish} style={{ marginLeft: 10 }}>強気 {bull.length}</Tag>
              <Tag color={colors.bearish}>弱気 {bear.length}</Tag>
            </span>
          ),
          children: (
            <div>
              {bull.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <Title level={5} style={{ color: colors.bullish, marginBottom: 8 }}>
                    <ArrowUpOutlined /> 強気 ({bull.length})
                  </Title>
                  <EventList events={bull} />
                </div>
              )}
              {bear.length > 0 && (
                <div>
                  <Title level={5} style={{ color: colors.bearish, marginBottom: 8 }}>
                    <ArrowDownOutlined /> 弱気 ({bear.length})
                  </Title>
                  <EventList events={bear} />
                </div>
              )}
            </div>
          ),
        };
      });
  }, [byMonth]);

  return (
    <Collapse
      items={items}
      defaultActiveKey={items.length > 0 ? [items[0].key] : []}
      style={{ background: "transparent" }}
    />
  );
}

// ──────────── 銘柄別ビュー ────────────
function SymbolView({ events }: { events: Event[] }) {
  const bySymbol = useMemo(() => {
    const m: Record<string, Event[]> = {};
    for (const e of events) {
      (m[e.symbol] ||= []).push(e);
    }
    return m;
  }, [events]);

  const items = useMemo(() => {
    const symbols = Object.keys(bySymbol).sort();
    return symbols.map(sym => {
      const arr = bySymbol[sym];
      const bull = arr.filter(e => e.direction === "bullish");
      const bear = arr.filter(e => e.direction === "bearish");
      return {
        key: sym,
        label: (
          <span>
            <b style={{ color: colors.textPrimary }}>{sym}</b>
            <Tag color={colors.bullish} style={{ marginLeft: 10 }}>強気 {bull.length}</Tag>
            <Tag color={colors.bearish}>弱気 {bear.length}</Tag>
          </span>
        ),
        children: <EventList events={arr.slice().sort((a, b) => a.month - b.month)} showMonth />,
      };
    });
  }, [bySymbol]);

  return (
    <Collapse items={items} style={{ background: "transparent" }} />
  );
}

// ──────────── チャート種別ビュー ────────────
function ChartView({ events }: { events: Event[] }) {
  const byChart = useMemo(() => {
    const m: Record<Chart, Event[]> = {} as any;
    for (const e of events) {
      (m[e.chart] ||= []).push(e);
    }
    return m;
  }, [events]);

  const order: Chart[] = ["table", "mean", "median", "neg_rate", "intramonth", "daily"];
  const items = useMemo(() => {
    return order
      .filter(c => (byChart[c] || []).length > 0)
      .map(c => {
        const arr = byChart[c];
        const bull = arr.filter(e => e.direction === "bullish");
        const bear = arr.filter(e => e.direction === "bearish");
        return {
          key: c,
          label: (
            <span>
              <b style={{ color: colors.textPrimary }}>{CHART_LABEL[c]}</b>
              <Text style={{ color: colors.textSecondary, marginLeft: 8, fontSize: 11 }}>
                {CHART_DESCRIPTION[c]}
              </Text>
              <Tag color={colors.bullish} style={{ marginLeft: 10 }}>強気 {bull.length}</Tag>
              <Tag color={colors.bearish}>弱気 {bear.length}</Tag>
            </span>
          ),
          children: <EventList events={arr.slice().sort(sortByStrength)} showMonth showSymbol />,
        };
      });
  }, [byChart]);

  return (
    <Collapse
      items={items}
      defaultActiveKey={items.length > 0 ? [items[0].key] : []}
      style={{ background: "transparent" }}
    />
  );
}

function sortByStrength(a: Event, b: Event): number {
  // 大まかにシグナル強度で降順ソート
  const av = strength(a);
  const bv = strength(b);
  return bv - av;
}

function strength(e: Event): number {
  const m = e.metric;
  if (e.period === "both") return 10000;  // 両期間一致は最強
  switch (e.chart) {
    case "mean": return Math.abs(m.mean ?? 0) * 100;
    case "median": return Math.abs(m.median ?? 0) * 100;
    case "neg_rate":
      return Math.abs((m.neg_rate ?? 0.5) - 0.5) * 200;
    case "table":
      return (Math.abs(m.mean ?? 0) + Math.abs(m.median ?? 0)) * 100;
    case "intramonth": return Math.abs(m.cum_end ?? 0) * 100;
    case "daily": return Math.abs(m.mean_pct ?? 0) * 100;
  }
  return 0;
}

// ──────────── イベントリスト ────────────
function EventList({
  events,
  showMonth = false,
  showSymbol = true,
}: {
  events: Event[];
  showMonth?: boolean;
  showSymbol?: boolean;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {events.map((e, i) => (
        <EventRow key={i} event={e} showMonth={showMonth} showSymbol={showSymbol} />
      ))}
    </div>
  );
}

function EventRow({
  event,
  showMonth,
  showSymbol,
}: {
  event: Event;
  showMonth: boolean;
  showSymbol: boolean;
}) {
  const text = event.period === "both" ? fmtMetricBoth(event) : fmtMetric(event);
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: "8px 12px",
      background: colors.bgPrimary,
      border: `1px solid ${colors.border}`,
      borderRadius: 6,
      borderLeft: `3px solid ${dirColor(event.direction)}`,
    }}>
      <span style={{ color: dirColor(event.direction), minWidth: 16 }}>
        {dirIcon(event.direction)}
      </span>
      {showMonth && (
        <Tag style={{ minWidth: 44, textAlign: "center", margin: 0 }}>
          {MONTH_NAMES[event.month - 1]}
        </Tag>
      )}
      {showSymbol && (
        <Link
          to={`/seasonality/${encodeURIComponent(event.symbol)}`}
          style={{ color: colors.accent, minWidth: 100, fontWeight: 600 }}
        >
          {event.symbol}
        </Link>
      )}
      <Tooltip title={CHART_DESCRIPTION[event.chart]}>
        <Tag style={{ margin: 0 }}>{CHART_LABEL[event.chart]}</Tag>
      </Tooltip>
      <Tag color={periodColor(event.period)} style={{ margin: 0 }}>
        {PERIOD_LABEL[event.period]}
      </Tag>
      <Text style={{ color: colors.textSecondary, fontSize: 12, marginLeft: "auto" }}>
        {text}
      </Text>
    </div>
  );
}
