"""
日経平均株価回帰モデル サービス

回帰式:
  Nikkei_model = a * AFRE_12MA + b * USDJPY + c
  - AFRE_12MA: 中国社会融資総量フロー 12ヶ月移動平均 (10億元)
  - USDJPY: ドル円月足終値
  - 学習期間: 2009年〜2018年

データソース:
  - AFRE: PBOC (既存 aggregate_financing サービス)
  - USDJPY: yfinance (JPY=X)
  - 日経平均: yfinance (^N225)

更新スケジュール: 社会融資総量更新時 + 日次（yfinanceデータ）
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nikkei_regression_cache.json"

# Redis
DATA_CACHE_KEY = "market:nikkei_regression:data"

# 学習期間
TRAIN_START_YEAR = 2009
TRAIN_END_YEAR = 2018

# AFRE Redis key (既存サービスのキャッシュを直接参照)
AFRE_REDIS_KEY = "china:cn_aggregate_financing:data"
AFRE_CACHE_FILE = (
    Path(__file__).parent.parent.parent
    / "data" / "cache" / "china" / "policy" / "cn_aggregate_financing_cache.json"
)

# 歴史CSV（2008年〜、PBOC API未カバー期間を補完）
HISTORICAL_CSV = (
    Path(__file__).parent.parent.parent
    / "data" / "csv_import" / "social_financing_flow.csv"
)


class NikkeiRegressionService:
    """日経平均株価回帰モデル サービス"""

    def _should_refresh(self) -> bool:
        """キャッシュの更新が必要かどうか判定"""
        try:
            cached = redis_client.get(DATA_CACHE_KEY)
            if not cached:
                return True

            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True

            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)

            # 6時間以内に更新されていればスキップ
            if (now - last_updated).total_seconds() < 6 * 3600:
                return False

            return True
        except Exception:
            return True

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """日経平均回帰モデルデータを取得"""
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        try:
            data = self._build_model()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"[NikkeiRegression] Model build error: {e}")
            import traceback
            traceback.print_exc()

        # フォールバック
        cached = self._load_from_redis()
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file()
        if cached and cached.get("data"):
            return cached

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "Nikkei Regression Model"},
            "model_info": None,
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _get_afre_flow_data(self) -> Dict[str, float]:
        """社会融資総量フローデータを取得（CSV + PBOC APIマージ）

        Returns:
            date(YYYY-MM-01) → flow(10億元) のマップ
        """
        flow_map: Dict[str, float] = {}

        # (1) 歴史CSV読み込み（2008年〜, 10億元単位）
        try:
            if HISTORICAL_CSV.exists():
                import csv
                with open(HISTORICAL_CSV, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        date_raw = row.get("date", "").strip()
                        val_raw = row.get("syakaiyuusi", "").strip()
                        if not date_raw or not val_raw:
                            continue
                        # MM/YYYY → YYYY-MM-01
                        parts = date_raw.split("/")
                        if len(parts) == 2:
                            month, year = parts
                            date_str = f"{year}-{month.zfill(2)}-01"
                            # カンマ区切り数値を処理
                            flow_map[date_str] = float(val_raw.replace(",", ""))
        except Exception as e:
            logger.error(f"[NikkeiRegression] CSV load error: {e}")

        # (2) PBOC APIデータで上書き（より新しいデータ優先）
        api_data = self._get_afre_api_data()
        for item in api_data:
            flow = item.get("flow")
            if flow is None:
                continue
            date_str = item["date"][:7] + "-01"
            # 億元 → 10億元
            flow_map[date_str] = flow / 10.0

        logger.info(
            f"[NikkeiRegression] AFRE flow: {len(flow_map)} months "
            f"({min(flow_map.keys()) if flow_map else 'N/A'} to "
            f"{max(flow_map.keys()) if flow_map else 'N/A'})"
        )
        return flow_map

    def _get_afre_api_data(self) -> List[Dict[str, Any]]:
        """PBOC APIデータを取得"""
        # まずRedisから
        try:
            cached = redis_client.get(AFRE_REDIS_KEY)
            if cached and cached.get("data"):
                return cached["data"]
        except Exception:
            pass

        # ファイルキャッシュフォールバック
        try:
            if AFRE_CACHE_FILE.exists():
                with open(AFRE_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("data"):
                    return data["data"]
        except Exception:
            pass

        # 直接APIを呼ぶ
        try:
            from services.china.cn_aggregate_financing_service import (
                cn_aggregate_financing_service,
            )
            result = cn_aggregate_financing_service.get_data()
            if result and result.get("data"):
                return result["data"]
        except Exception as e:
            logger.error(f"[NikkeiRegression] Failed to get AFRE data: {e}")

        return []

    def _get_monthly_yfinance(
        self, ticker_symbol: str, start_date: str = "2007-01-01"
    ) -> Dict[str, float]:
        """yfinanceから月足終値を取得（date→close マップ）"""
        import yfinance as yf

        ticker = yf.Ticker(ticker_symbol)
        end_dt = datetime.now(JST) + timedelta(days=5)
        hist = ticker.history(
            start=start_date,
            end=end_dt.strftime("%Y-%m-%d"),
            interval="1mo",
        )

        if hist.empty:
            logger.warning(
                f"[NikkeiRegression] No yfinance data for {ticker_symbol}"
            )
            return {}

        result: Dict[str, float] = {}
        for idx, row in hist.iterrows():
            date_str = idx.strftime("%Y-%m-01")
            result[date_str] = round(float(row["Close"]), 2)

        return result

    def _compute_afre_12ma(
        self, flow_map: Dict[str, float]
    ) -> Dict[str, float]:
        """社会融資総量フロー12ヶ月移動平均を計算

        flow_map: date(YYYY-MM-01) → flow(10億元) のマップ
        """
        sorted_months = sorted(flow_map.keys())
        ma_result: Dict[str, float] = {}
        for i, month in enumerate(sorted_months):
            if i < 11:
                continue
            window = sorted_months[i - 11 : i + 1]
            values = [flow_map[m] for m in window]
            ma_result[month] = round(sum(values) / 12.0, 3)

        return ma_result

    def _run_regression(
        self,
        afre_12ma: Dict[str, float],
        usdjpy: Dict[str, float],
        nikkei: Dict[str, float],
    ) -> Optional[Tuple[np.ndarray, float, Dict[str, Any]]]:
        """線形回帰を実行

        Returns:
            (coefficients [a, b], intercept, model_info) or None
        """
        # 学習データを構築（共通日付のみ）
        train_dates = []
        X_train = []
        y_train = []

        for date_str in sorted(afre_12ma.keys()):
            year = int(date_str[:4])
            if year < TRAIN_START_YEAR or year > TRAIN_END_YEAR:
                continue
            if date_str not in usdjpy or date_str not in nikkei:
                continue

            train_dates.append(date_str)
            X_train.append([afre_12ma[date_str], usdjpy[date_str]])
            y_train.append(nikkei[date_str])

        if len(X_train) < 10:
            logger.warning(
                f"[NikkeiRegression] Insufficient training data: {len(X_train)} points"
            )
            return None

        X = np.array(X_train)
        y = np.array(y_train)

        # 切片項を追加
        X_with_intercept = np.column_stack([X, np.ones(len(X))])

        # 最小二乗法
        result = np.linalg.lstsq(X_with_intercept, y, rcond=None)
        params = result[0]  # [a, b, c]
        coefficients = params[:2]
        intercept = params[2]

        # R² 計算
        y_pred = X_with_intercept @ params
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        model_info = {
            "coef_afre_12ma": round(float(coefficients[0]), 4),
            "coef_usdjpy": round(float(coefficients[1]), 4),
            "intercept": round(float(intercept), 4),
            "r_squared": round(float(r_squared), 4),
            "train_period": f"{TRAIN_START_YEAR}-{TRAIN_END_YEAR}",
            "train_samples": len(X_train),
            "train_start": train_dates[0],
            "train_end": train_dates[-1],
        }

        logger.info(
            f"[NikkeiRegression] Model: Nikkei = "
            f"{model_info['coef_afre_12ma']}*AFRE_12MA + "
            f"{model_info['coef_usdjpy']}*USDJPY + "
            f"{model_info['intercept']}, R²={model_info['r_squared']}"
        )

        return coefficients, intercept, model_info

    def _build_model(self) -> Optional[Dict[str, Any]]:
        """モデルを構築しデータを返す"""
        logger.info("[NikkeiRegression] Building regression model...")

        # 1. 社会融資総量フローデータ
        afre_data = self._get_afre_flow_data()
        if not afre_data:
            logger.error("[NikkeiRegression] No AFRE flow data available")
            return None

        # 2. 12MA計算
        afre_12ma = self._compute_afre_12ma(afre_data)
        if not afre_12ma:
            logger.error("[NikkeiRegression] Could not compute AFRE 12MA")
            return None

        # 3. yfinance: USDJPY月足, 日経平均月足
        usdjpy = self._get_monthly_yfinance("JPY=X")
        nikkei = self._get_monthly_yfinance("^N225")

        if not usdjpy or not nikkei:
            logger.error("[NikkeiRegression] Could not get yfinance data")
            return None

        # 4. 回帰
        reg_result = self._run_regression(afre_12ma, usdjpy, nikkei)
        if reg_result is None:
            return None

        coefficients, intercept, model_info = reg_result

        # 5. 全期間の予測値を生成（2009年〜）
        result_data: List[Dict[str, Any]] = []
        all_dates = sorted(
            set(afre_12ma.keys()) & set(usdjpy.keys()) & set(nikkei.keys())
        )

        for date_str in all_dates:
            year = int(date_str[:4])
            if year < TRAIN_START_YEAR:
                continue

            predicted = (
                coefficients[0] * afre_12ma[date_str]
                + coefficients[1] * usdjpy[date_str]
                + intercept
            )

            result_data.append({
                "date": date_str,
                "actual": nikkei[date_str],
                "model": round(float(predicted), 0),
            })

        # AFRE 12MAが日経データより先にある月はモデル値のみ追加
        nikkei_dates = set(nikkei.keys())
        for date_str in sorted(afre_12ma.keys()):
            year = int(date_str[:4])
            if year < TRAIN_START_YEAR:
                continue
            if date_str in nikkei_dates:
                continue  # 既に含まれている
            if date_str not in usdjpy:
                continue

            predicted = (
                coefficients[0] * afre_12ma[date_str]
                + coefficients[1] * usdjpy[date_str]
                + intercept
            )
            result_data.append({
                "date": date_str,
                "actual": None,
                "model": round(float(predicted), 0),
            })

        # 日経平均がAFRE 12MAより先にある月は実績値のみ追加
        existing_dates = {d["date"] for d in result_data}
        for date_str in sorted(nikkei.keys()):
            year = int(date_str[:4])
            if year < TRAIN_START_YEAR:
                continue
            if date_str in existing_dates:
                continue  # 既に含まれている
            result_data.append({
                "date": date_str,
                "actual": nikkei[date_str],
                "model": None,
            })

        result_data.sort(key=lambda x: x["date"])

        if not result_data:
            return None

        latest = result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        return {
            "data": result_data,
            "latest": latest,
            "model_info": model_info,
            "metadata": {
                "source": "Regression Model (AFRE 12MA + USDJPY)",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
                "afre_latest": max(afre_12ma.keys()),
                "usdjpy_latest": max(usdjpy.keys()),
                "nikkei_latest": max(nikkei.keys()),
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(DATA_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[NikkeiRegression] Redis save error: {e}")

        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[NikkeiRegression] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[NikkeiRegression] Redis load error: {e}")
        return None

    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        try:
            if DATA_CACHE_FILE.exists():
                with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception as e:
            logger.error(f"[NikkeiRegression] File load error: {e}")
        return None


# シングルトン
nikkei_regression_service = NikkeiRegressionService()
