"""
シカゴ連銀失業率予測サービス

Chicago Fed Labor Market Indicators の Excel ファイルから
失業率予測（Real-Time Unemployment Rate Forecast）および
雇用フローレート（採用率／離職率／フロー一貫失業率）を取得する。

データソース:
- Excel URL: https://www.chicagofed.org/-/media/publications/chicago-fed-labor-market-indicators/chi-labor-market-indicators.xlsx
- リリーススケジュール: https://www.chicagofed.org/research/data/chicago-fed-labor-market-indicators/release-schedule
- 発表時刻: 8:30 a.m. ET（月2回 — Advance / Final）

更新スケジュール: 月2回（発表スケジュール参照、Chicago Fed Labor Market Indicators）
- 発表スケジュールは半期更新（1月／7月想定）。スケジュールキャッシュは [[chicago-fed-labor-market-schedule]] で管理。
"""
import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from core.redis_client import redis_client
from services.usa.chicago_fed_labor_market_schedule_utils import (
    expected_reference_date_from_label,
    get_last_release,
    get_next_release,
    should_refresh_by_schedule,
)

JST = ZoneInfo("Asia/Tokyo")

# 発表後にデータがまだ更新されていない場合の再取得最小間隔（30分）
POST_RELEASE_RETRY_INTERVAL_MINUTES = 30

# 発表期待月の参照日との許容ギャップ（日）— Excel の reference week は月中〜月後半に出るため
DATA_FRESHNESS_BUFFER_DAYS = 14


EXCEL_URL = (
    "https://www.chicagofed.org/-/media/publications/chicago-fed-labor-market-indicators/"
    "chi-labor-market-indicators.xlsx?sc_lang=en&hash=2E90EFE1C90BE679DA3702B04522C8EA"
)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "usa" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "chicago_fed_unemployment_rate_forecast_cache.json"

DATA_CACHE_KEY = "chicagofed:unemployment_rate_forecast:data"

# Sheet 1（Rates）の列
RATES_COLUMNS = ["layoffs_other_seps", "hiring_rate_uw", "fcr", "s_cps", "f_cps"]
# Sheet 2（UR Forecast）の列
FORECAST_COLUMNS = [
    "forecast16a", "forecast25a", "forecast50a", "forecast75a", "forecast84a",
    "forecast16f", "forecast25f", "forecast50f", "forecast75f", "forecast84f",
    "forecast16r", "forecast25r", "forecast50r", "forecast75r", "forecast84r",
    "official_u3",
]
# Sheet 4 — 1-month forecast probability の 7バケット (順序維持)
PROB_BUCKETS_1M = [
    ("bucket_neg_03_or_lower", "<= -0.3 pp", -0.3),
    ("bucket_neg_02",          "-0.2 pp",    -0.2),
    ("bucket_neg_01",          "-0.1 pp",    -0.1),
    ("bucket_no_change",       "No change",  0.0),
    ("bucket_pos_01",          "+0.1 pp",    0.1),
    ("bucket_pos_02",          "+0.2 pp",    0.2),
    ("bucket_pos_03_or_higher", ">= +0.3 pp", 0.3),
]


class ChicagoFedUnemploymentRateForecastService:
    """シカゴ連銀失業率予測サービス"""

    def get_chicago_fed_unemployment_rate_forecast_data(
        self,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        失業率予測データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [...],                  # rates と forecast をマージした時系列
                "rates_data": [...],            # 雇用フローレート時系列（Sheet 1）
                "forecast_data": [...],         # 失業率予測時系列（Sheet 2）
                "latest": {...},                # 最新の予測（forecast50f 中心）
                "latest_rates": {...},          # 最新の雇用フローレート
                "next_release": {...} | None,
                "metadata": {...},
                "cached": bool,
                "source": str,
                "last_updated": str,
            }
        """
        if not force_refresh:
            cached = redis_client.get(DATA_CACHE_KEY)
            if cached:
                last_updated_str = cached.get("last_updated")
                if (
                    last_updated_str
                    and not should_refresh_by_schedule(last_updated_str)
                    and not self._is_data_stale_post_release(cached)
                ):
                    return self._build_response(cached, cached_=True, source="redis")

            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if (
                    last_updated_str
                    and not should_refresh_by_schedule(last_updated_str)
                    and not self._is_data_stale_post_release(file_cache)
                ):
                    redis_client.set(DATA_CACHE_KEY, file_cache, expire=0)
                    return self._build_response(file_cache, cached_=True, source="file")

        try:
            payload = self._fetch_from_excel()
        except Exception as e:
            print(f"Error fetching Chicago Fed Labor Market Excel: {e}")
            # フェッチ試行時刻だけは更新（取りこぼし再試行のレート制限）
            cached = redis_client.get(DATA_CACHE_KEY) or self._load_file_cache()
            if cached:
                cached["last_fetch_attempt"] = datetime.now(JST).isoformat()
                redis_client.set(DATA_CACHE_KEY, cached, expire=0)
                self._save_file_cache(cached)
                return self._build_response(cached, cached_=True, source="fallback")
            return {
                "data": [],
                "rates_data": [],
                "forecast_data": [],
                "probability_data": [],
                "latest": None,
                "latest_rates": None,
                "latest_probability": None,
                "next_release": get_next_release(),
                "metadata": {},
                "cached": False,
                "source": "none",
                "last_updated": None,
                "error": str(e),
            }

        # フェッチ試行時刻も保存 — 取得成功でもデータが進まないケースのリトライ制限
        payload["last_fetch_attempt"] = datetime.now(JST).isoformat()
        redis_client.set(DATA_CACHE_KEY, payload, expire=0)
        self._save_file_cache(payload)
        return self._build_response(payload, cached_=False, source="excel")

    def _is_data_stale_post_release(self, cached_payload: Dict[str, Any]) -> bool:
        """
        発表時刻は過ぎているのに、Excel のデータが追従していないケースを検出

        ロジック:
        - 直近の過去発表 (例: '2026-05-28 May 2026 Advance') を取得
        - 期待される参照月 (例: 2026-05) を label から推定
        - 期待月の中ごろ -14日 を「fresh の閾値」とし、cached.latest が
          この閾値より古ければ「データ未更新」と判定
        - ただし `last_fetch_attempt` から 30分以内なら再取得しない (レート制限)

        Returns:
            True: 取りこぼし状態（再取得すべき）
            False: データは最新、またはリトライ待機中
        """
        last_release = get_last_release()
        if not last_release:
            return False

        expected_ref = expected_reference_date_from_label(last_release.get("label"))
        if not expected_ref:
            return False

        # キャッシュ済み latest 行の date
        latest = cached_payload.get("latest") or {}
        latest_date_str = latest.get("date")
        # forecast_data の最新行 date も合わせて確認（より厳密）
        forecast_data = cached_payload.get("forecast_data") or []
        latest_forecast_date_str = forecast_data[-1].get("date") if forecast_data else None

        # 直近 forecast_data の最大 date を採用
        candidates = [d for d in [latest_date_str, latest_forecast_date_str] if d]
        if not candidates:
            return True
        max_data_date_str = max(candidates)
        try:
            max_data_date = datetime.strptime(max_data_date_str, "%Y-%m-%d").date()
        except ValueError:
            return True

        # 期待参照月の中ごろから -14日 を fresh 閾値とする
        fresh_threshold = expected_ref - timedelta(days=DATA_FRESHNESS_BUFFER_DAYS)
        if max_data_date >= fresh_threshold:
            return False  # データは最新

        # データ未更新 — レート制限チェック
        last_attempt_str = cached_payload.get("last_fetch_attempt") or cached_payload.get("last_updated")
        if last_attempt_str:
            try:
                last_attempt_dt = datetime.fromisoformat(last_attempt_str)
                if last_attempt_dt.tzinfo is None:
                    last_attempt_dt = last_attempt_dt.replace(tzinfo=JST)
                minutes_since_attempt = (
                    datetime.now(JST) - last_attempt_dt
                ).total_seconds() / 60
                if minutes_since_attempt < POST_RELEASE_RETRY_INTERVAL_MINUTES:
                    # 直近のリトライから30分以内 → 待機
                    return False
            except Exception:
                pass

        print(
            f"[Chicago Fed UR Forecast] Data appears stale post-release. "
            f"max_data_date={max_data_date}, expected_ref={expected_ref}, "
            f"last_release={last_release.get('label')}"
        )
        return True

    def _build_response(
        self,
        payload: Dict[str, Any],
        cached_: bool,
        source: str,
    ) -> Dict[str, Any]:
        return {
            "data": payload.get("data", []),
            "rates_data": payload.get("rates_data", []),
            "forecast_data": payload.get("forecast_data", []),
            "probability_data": payload.get("probability_data", []),
            "latest": payload.get("latest"),
            "latest_rates": payload.get("latest_rates"),
            "latest_probability": payload.get("latest_probability"),
            "next_release": get_next_release(),
            "metadata": payload.get("metadata", {}),
            "cached": cached_,
            "source": source,
            "last_updated": payload.get("last_updated"),
        }

    def _fetch_from_excel(self) -> Dict[str, Any]:
        """Excel ファイルをダウンロードし、Rates と UR Forecast をパース"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        }
        resp = requests.get(EXCEL_URL, headers=headers, timeout=120)
        resp.raise_for_status()
        buf = io.BytesIO(resp.content)

        rates_data = self._parse_rates_sheet(buf)
        buf.seek(0)
        forecast_data = self._parse_forecast_sheet(buf)
        buf.seek(0)
        probability_data = self._parse_probability_sheet(buf)

        # 日付ベースでマージ（rates_data がベース、forecast がオーバーレイ）
        merged: Dict[str, Dict[str, Any]] = {item["date"]: dict(item) for item in rates_data}
        for fitem in forecast_data:
            date_key = fitem["date"]
            row = merged.setdefault(date_key, {"date": date_key})
            for k, v in fitem.items():
                if k == "date":
                    continue
                row[k] = v
        merged_data = sorted(merged.values(), key=lambda x: x["date"])

        # 最新値（forecast50f を持つ最新行）
        latest = None
        for row in reversed(merged_data):
            if row.get("forecast50f") is not None or row.get("forecast50a") is not None:
                latest = row
                break

        # 最新の雇用フローレート
        latest_rates = None
        for row in reversed(rates_data):
            if any(row.get(k) is not None for k in RATES_COLUMNS):
                latest_rates = row
                break

        # 最新の確率分布: 同一 date 内では final 優先、final が無ければ advance
        latest_probability = self._select_latest_probability(probability_data, merged_data)

        metadata = {
            "source": "Chicago Fed Labor Market Indicators (chi-labor-market-indicators.xlsx)",
            "source_url": (
                "https://www.chicagofed.org/research/data/"
                "chicago-fed-labor-market-indicators/latest-release"
            ),
            "rates_columns": RATES_COLUMNS,
            "forecast_columns": FORECAST_COLUMNS,
            "probability_buckets_1m": [{"key": k, "label": l, "delta": d} for k, l, d in PROB_BUCKETS_1M],
            "rates_unit": "%",
            "forecast_unit": "%",
            "probability_unit": "%",
            "rates_count": len(rates_data),
            "forecast_count": len(forecast_data),
            "probability_count": len(probability_data),
        }

        return {
            "data": merged_data,
            "rates_data": rates_data,
            "forecast_data": forecast_data,
            "probability_data": probability_data,
            "latest": latest,
            "latest_rates": latest_rates,
            "latest_probability": latest_probability,
            "metadata": metadata,
            "last_updated": datetime.now().astimezone().isoformat(),
        }

    def _parse_rates_sheet(self, buf: io.BytesIO) -> List[Dict[str, Any]]:
        """Sheet 1 '1. Rates' をパース"""
        df = pd.read_excel(buf, sheet_name="1. Rates", header=0)
        if df.empty:
            return []
        # 日付列を YYYY-MM-DD 文字列に変換
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        df = df.dropna(subset=["date"])

        result: List[Dict[str, Any]] = []
        # Excel 列: layoffs_other_seps, hiring_rate_uw, fcr, s, f
        for _, row in df.iterrows():
            result.append({
                "date": str(row["date"]),
                "layoffs_other_seps": self._to_float(row.get("layoffs_other_seps")),
                "hiring_rate_uw": self._to_float(row.get("hiring_rate_uw")),
                "fcr": self._to_float(row.get("fcr")),
                "s_cps": self._to_float(row.get("s")),
                "f_cps": self._to_float(row.get("f")),
            })
        result.sort(key=lambda x: x["date"])
        return result

    def _parse_forecast_sheet(self, buf: io.BytesIO) -> List[Dict[str, Any]]:
        """Sheet 2 '2. Chicago Fed Real-Time UR' をパース

        Row 0: グループヘッダー (Advance / Final / Revised / BLS)
        Row 1: カラム名
        Row 2+: データ
        """
        df = pd.read_excel(
            buf,
            sheet_name="2. Chicago Fed Real-Time UR",
            header=1,
        )
        if df.empty:
            return []
        if "date" not in df.columns:
            return []
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        df = df.dropna(subset=["date"])

        result: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            entry: Dict[str, Any] = {"date": str(row["date"])}
            for col in FORECAST_COLUMNS:
                entry[col] = self._to_float(row.get(col)) if col in df.columns else None
            result.append(entry)
        result.sort(key=lambda x: x["date"])
        return result

    def _parse_probability_sheet(self, buf: io.BytesIO) -> List[Dict[str, Any]]:
        """Sheet 4 '4. Real-Time UR Probs' をパース

        Row 0: グループヘッダー
        Row 1: カラム名（date, release, バケット名...）
        Row 2+: データ（同一 date で advance と final の2行）
        """
        df = pd.read_excel(
            buf,
            sheet_name="4. Real-Time UR Probs",
            header=1,
        )
        if df.empty or "date" not in df.columns or "release" not in df.columns:
            return []
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        df = df.dropna(subset=["date"])

        result: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            buckets: Dict[str, Optional[float]] = {}
            for key, label, _delta in PROB_BUCKETS_1M:
                buckets[key] = self._to_float(row.get(label)) if label in df.columns else None

            # Relative Odds 計算（負変動の合計、正変動の合計、ネット）
            decrease = sum(
                v for k, v in buckets.items()
                if k in {"bucket_neg_03_or_lower", "bucket_neg_02", "bucket_neg_01"} and v is not None
            )
            increase = sum(
                v for k, v in buckets.items()
                if k in {"bucket_pos_01", "bucket_pos_02", "bucket_pos_03_or_higher"} and v is not None
            )
            has_any = any(v is not None for v in buckets.values())
            net = round(increase - decrease, 2) if has_any else None

            result.append({
                "date": str(row["date"]),
                "release": str(row.get("release", "")).strip().lower() or "unknown",
                "buckets": buckets,
                "relative_odds": {
                    "increase": round(increase, 2) if has_any else None,
                    "decrease": round(decrease, 2) if has_any else None,
                    "net": net,
                },
            })
        # 日付昇順 + advance → final の順
        result.sort(key=lambda x: (x["date"], 0 if x["release"] == "advance" else 1))
        return result

    def _select_latest_probability(
        self,
        probability_data: List[Dict[str, Any]],
        merged_data: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        最新の確率分布レコードを選択し、ベースライン UR と推定 UR レベルを付加

        - 同一 date 内では final 優先、無ければ advance
        - baseline_ur: 予測時点で最も新しい official_u3
        - bucket_ur_levels: 各バケットの暗黙 UR % 水準（baseline + delta）
        """
        if not probability_data:
            return None

        # 最新 date を持つ final、無ければ advance
        latest_date = max(p["date"] for p in probability_data)
        candidates = [p for p in probability_data if p["date"] == latest_date]
        prefer_final = [p for p in candidates if p["release"] == "final"]
        latest = (prefer_final or candidates)[0]

        # ベースライン UR: 予測時点の直近 official_u3（latest_date 以前の最も新しい非None値）
        baseline_ur: Optional[float] = None
        for row in reversed(merged_data):
            if row["date"] > latest_date:
                continue
            u3 = row.get("official_u3")
            if u3 is not None:
                baseline_ur = float(u3)
                break

        # 各バケットの推定 UR レベル
        bucket_ur_levels: Dict[str, Optional[float]] = {}
        if baseline_ur is not None:
            for key, _label, delta in PROB_BUCKETS_1M:
                bucket_ur_levels[key] = round(baseline_ur + delta, 2)
        else:
            for key, _label, _delta in PROB_BUCKETS_1M:
                bucket_ur_levels[key] = None

        return {
            **latest,
            "baseline_ur": baseline_ur,
            "bucket_ur_levels": bucket_ur_levels,
        }

    @staticmethod
    def _to_float(v: Any) -> Optional[float]:
        try:
            if v is None:
                return None
            if pd.isna(v):
                return None
            return float(v)
        except (TypeError, ValueError):
            return None

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        if not DATA_CACHE_FILE.exists():
            return None
        try:
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading Chicago Fed UR Forecast file cache: {e}")
            return None

    def _save_file_cache(self, payload: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving Chicago Fed UR Forecast file cache: {e}")

    def invalidate_cache(self) -> bool:
        try:
            redis_client.delete(DATA_CACHE_KEY)
            if DATA_CACHE_FILE.exists():
                DATA_CACHE_FILE.unlink()
            return True
        except Exception as e:
            print(f"Error invalidating Chicago Fed UR Forecast cache: {e}")
            return False


chicago_fed_unemployment_rate_forecast_service = ChicagoFedUnemploymentRateForecastService()
