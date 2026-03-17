"""
価格転嫁率（中小企業庁・コスト全般）サービス

中小企業庁「価格交渉促進月間」フォローアップ調査結果から
価格転嫁率を自動取得・DB蓄積・提供する。

データソース:
- 中小企業庁 価格交渉促進月間フォローアップ調査
- PDF配布: https://www.chusho.meti.go.jp/keiei/torihiki/follow-up/
- 半年ごと（3月調査・9月調査）

系列:
- total: コスト全般（全体）
- raw_materials: 原材料費
- energy: エネルギー費
- labor: 労務費
- zero_pass_through: 全く転嫁できず割合
- supply_chain: サプライチェーン段階別転嫁率（1次〜4次請け）

ストレージ: PostgreSQL price_pass_through_rate テーブル
キャッシュ: Redis → ファイル → DB
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "price"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "price_pass_through_rate_cache.json"

# ---------------------------------------------------------------------------
# PDF URL パターン（調査月ベース）
# ---------------------------------------------------------------------------
PDF_URL_TEMPLATE = (
    "https://www.chusho.meti.go.jp/keiei/torihiki/follow-up/dl/{yyyymm}/result_01.pdf"
)

# 調査月リスト（3月と9月に実施）
SURVEY_MONTHS = [3, 9]


class PricePassThroughRateService:
    """価格転嫁率（中小企業庁）サービス"""

    DATA_CACHE_KEY = "japan:price_pass_through_rate:data"

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """価格転嫁率データを取得"""
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                cached_data["cached"] = True
                cached_data["source"] = "redis"
                return cached_data

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                file_cache["cached"] = True
                file_cache["source"] = "file"
                return file_cache

        # force_refresh: PDF自動取得 → DB保存
        if force_refresh:
            self._fetch_and_store_new_periods()

        # DBから読み出し
        data = self._load_from_db()
        if not data:
            # DBが空の場合（通常ありえない）
            return {
                "data": [],
                "latest": None,
                "metadata": self._metadata(),
                "last_updated": datetime.now(JST).isoformat(),
                "cached": False,
                "source": "empty",
            }

        result = self._wrap_response(data)
        redis_client.set(self.DATA_CACHE_KEY, result, expire=0)
        self._save_file_cache(result)
        result["cached"] = False
        result["source"] = "database"
        return result

    # ------------------------------------------------------------------
    # DB操作
    # ------------------------------------------------------------------

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから全レコードを読み出し"""
        try:
            from core.database import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT survey_date, survey_period, total, raw_materials,
                               energy, labor, zero_pass_through, supply_chain
                        FROM price_pass_through_rate
                        ORDER BY survey_date ASC
                        """
                    )
                    rows = cur.fetchall()

            result = []
            for row in rows:
                survey_date, survey_period, total, raw_materials, energy, labor, zero_pct, sc = row
                record = {
                    "date": survey_date.strftime("%Y-%m-%d"),
                    "survey_period": survey_period,
                    "total": float(total),
                    "raw_materials": float(raw_materials) if raw_materials is not None else None,
                    "energy": float(energy) if energy is not None else None,
                    "labor": float(labor) if labor is not None else None,
                    "zero_pass_through": float(zero_pct) if zero_pct is not None else None,
                    "supply_chain": sc,  # JSONB → dict or None
                }
                result.append(record)
            return result

        except Exception as e:
            print(f"[PricePassThrough] DB read error: {e}")
            return []

    def _upsert_record(self, record: Dict[str, Any]) -> bool:
        """1レコードをDBにupsert"""
        try:
            from core.database import get_db_connection

            sc_json = json.dumps(record["supply_chain"]) if record.get("supply_chain") else None

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO price_pass_through_rate
                            (survey_date, survey_period, total, raw_materials, energy, labor,
                             zero_pass_through, supply_chain, source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pdf_extracted')
                        ON CONFLICT (survey_date) DO UPDATE SET
                            total = EXCLUDED.total,
                            raw_materials = EXCLUDED.raw_materials,
                            energy = EXCLUDED.energy,
                            labor = EXCLUDED.labor,
                            zero_pass_through = EXCLUDED.zero_pass_through,
                            supply_chain = EXCLUDED.supply_chain,
                            source = EXCLUDED.source,
                            updated_at = NOW()
                        """,
                        (
                            record["date"],
                            record["survey_period"],
                            record["total"],
                            record.get("raw_materials"),
                            record.get("energy"),
                            record.get("labor"),
                            record.get("zero_pass_through"),
                            sc_json,
                        ),
                    )
                conn.commit()
            return True

        except Exception as e:
            print(f"[PricePassThrough] DB upsert error: {e}")
            return False

    # ------------------------------------------------------------------
    # PDF自動取得 → DB保存
    # ------------------------------------------------------------------

    def _fetch_and_store_new_periods(self) -> None:
        """未取得の候補期をPDFから取得してDBに保存"""
        existing_dates = set()
        try:
            from core.database import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT survey_date FROM price_pass_through_rate")
                    existing_dates = {row[0].strftime("%Y-%m-%d") for row in cur.fetchall()}
        except Exception as e:
            print(f"[PricePassThrough] DB read error for candidates: {e}")
            return

        candidates = self._get_candidate_periods(existing_dates)
        for year, month in candidates:
            record = self._fetch_and_parse_pdf(year, month)
            if record:
                if self._upsert_record(record):
                    print(f"[PricePassThrough] Stored in DB: {record['survey_period']}")

    def _get_candidate_periods(self, existing_dates: set) -> List[tuple]:
        """取得すべき候補期を返す"""
        now = datetime.now(JST)
        candidates = []

        # 2026-03 以降の未取得期をチェック
        start_year = 2026
        for year in range(start_year, now.year + 2):
            for month in SURVEY_MONTHS:
                date_str = f"{year}-{month:02d}-01"
                if date_str not in existing_dates:
                    candidates.append((year, month))

        return candidates[:4]  # 最大4期

    # ------------------------------------------------------------------
    # PDF取得・解析
    # ------------------------------------------------------------------

    def _fetch_and_parse_pdf(
        self, survey_year: int, survey_month: int
    ) -> Optional[Dict[str, Any]]:
        """調査月のPDFを取得してデータを抽出"""
        try:
            import requests
        except ImportError:
            print("[PricePassThrough] requests not available")
            return None

        yyyymm = f"{survey_year}{survey_month:02d}"
        url = PDF_URL_TEMPLATE.format(yyyymm=yyyymm)

        try:
            print(f"[PricePassThrough] Fetching PDF: {url}")
            resp = requests.get(
                url,
                timeout=180,
                headers={"User-Agent": "Mozilla/5.0 (EconAlpha)"},
            )
            if resp.status_code != 200:
                print(f"[PricePassThrough] HTTP {resp.status_code} for {url}")
                return None

            if len(resp.content) < 10000:
                print(f"[PricePassThrough] PDF too small ({len(resp.content)} bytes)")
                return None

            record = self._parse_pdf(resp.content, survey_year, survey_month)
            if record:
                print(f"[PricePassThrough] Extracted: total={record['total']}%")
            return record

        except Exception as e:
            print(f"[PricePassThrough] Error fetching {url}: {e}")
            return None

    def _parse_pdf(
        self, pdf_bytes: bytes, survey_year: int, survey_month: int
    ) -> Optional[Dict[str, Any]]:
        """PDFバイトからpdfplumberでテキスト抽出し、各系列の転嫁率を取得"""
        try:
            import io
            import pdfplumber

            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                full_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"

            if not full_text:
                return None

            # --- 主要4系列の抽出 ---
            total, raw_materials, energy, labor = self._extract_main_series(full_text)

            if total is None:
                print("[PricePassThrough] Could not extract total rate")
                return None

            # --- 全く転嫁できず割合 ---
            zero_pct = self._extract_zero_pass_through(full_text)

            # --- サプライチェーン段階別 ---
            supply_chain = self._extract_supply_chain(full_text)

            # 妥当性チェック
            for val in [total, raw_materials, energy, labor]:
                if val is not None and (val < 0 or val > 100):
                    print(f"[PricePassThrough] Invalid value: {val}")
                    return None

            return {
                "date": f"{survey_year}-{survey_month:02d}-01",
                "survey_period": f"{survey_year}年{survey_month}月",
                "total": total,
                "raw_materials": raw_materials,
                "energy": energy,
                "labor": labor,
                "zero_pass_through": zero_pct,
                "supply_chain": supply_chain,
            }

        except ImportError:
            print("[PricePassThrough] pdfplumber not installed")
            return None
        except Exception as e:
            print(f"[PricePassThrough] Error parsing PDF: {e}")
            return None

    # ------------------------------------------------------------------
    # 系列抽出ロジック
    # ------------------------------------------------------------------

    def _extract_main_series(self, text: str) -> tuple:
        """
        主要4系列（全体・原材料費・エネルギー費・労務費）を抽出。

        テーブル行パターン:
          全体 ↑ 53.5% (52.4%) ↑ 55.0% (54.5%) ↑ 48.9% (47.8%) ↑ 50.0% (48.6%)
          列順: コスト全般 / 原材料費 / エネルギー費 / 労務費
        """
        # Method 1: テーブル行から4系列同時抽出
        m = re.search(
            r"全体\s*[↑↓→]+\s*(\d+\.?\d*)%\s*\([^)]+\)\s*"
            r"[↑↓→]+\s*(\d+\.?\d*)%\s*\([^)]+\)\s*"
            r"[↑↓→]+\s*(\d+\.?\d*)%\s*\([^)]+\)\s*"
            r"[↑↓→]+\s*(\d+\.?\d*)%",
            text,
        )
        if m:
            return (
                float(m.group(1)),
                float(m.group(2)),
                float(m.group(3)),
                float(m.group(4)),
            )

        # Method 2: ヘッダーから全体のみ + 個別抽出
        total = None
        m2 = re.search(
            r"コスト全体の価格転嫁率は\s*(\d+\.?\d*)\s*[％%]", text
        )
        if m2:
            total = float(m2.group(1))

        raw = self._extract_single_rate(
            text, r"原材料費?\D{0,30}?転嫁率[：:]\s*(\d+\.?\d*)\s*[％%]"
        )
        eng = self._extract_single_rate(
            text, r"エネルギー[費コスト]*\D{0,30}?転嫁率[：:]\s*(\d+\.?\d*)\s*[％%]"
        )
        lab = self._extract_single_rate(
            text, r"労務費?\D{0,30}?転嫁率[：:]\s*(\d+\.?\d*)\s*[％%]"
        )

        return (total, raw, eng, lab)

    def _extract_zero_pass_through(self, text: str) -> Optional[float]:
        """
        「全く転嫁できず」割合を抽出。

        パターン: ⑥{前回}% ： 全く転嫁できず ⑥{今回}%
        """
        # ⑥{数値}% ： 全く転嫁できず ⑥{数値}%
        m = re.search(
            r"⑥\s*(\d+\.?\d*)\s*%\s*[：:]\s*全く転嫁でき(?:ず|なかった)\s*⑥\s*(\d+\.?\d*)\s*%",
            text,
        )
        if m:
            return float(m.group(2))  # 右側が最新

        # フォールバック: 単独パターン
        m2 = re.search(
            r"全く転嫁でき(?:ず|なかった)[^0-9]{0,20}(\d+\.?\d*)\s*[％%]",
            text,
        )
        if m2:
            val = float(m2.group(1))
            if 0 < val < 20:
                return val

        return None

    def _extract_supply_chain(self, text: str) -> Optional[Dict[str, float]]:
        """
        サプライチェーン段階別転嫁率を抽出。

        パターン: {N}次請け ... {転嫁率}％（行末付近の数値）
        """
        result = {}
        tier_map = {
            "１次請け": "tier_1",
            "２次請け": "tier_2",
            "３次請け": "tier_3",
            "４次請け以上": "tier_4_plus",
        }

        for jp_name, key in tier_map.items():
            pattern = re.escape(jp_name) + r".*?(\d+\.?\d*)\s*[％%]\s*$"
            m = re.search(pattern, text, re.MULTILINE)
            if m:
                val = float(m.group(1))
                if 0 < val < 100:
                    result[key] = val

        return result if len(result) >= 2 else None

    def _extract_single_rate(self, text: str, pattern: str) -> Optional[float]:
        """正規表現で転嫁率を1つ抽出"""
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                val = float(m.group(1))
                if 0 <= val <= 100:
                    return val
            except ValueError:
                pass
        return None

    # ------------------------------------------------------------------
    # レスポンス構築
    # ------------------------------------------------------------------

    def _wrap_response(self, data: List[Dict]) -> Dict[str, Any]:
        """データをAPIレスポンス形式に包む"""
        latest = data[-1] if data else None
        now = datetime.now(JST)
        return {
            "data": data,
            "latest": latest,
            "metadata": self._metadata(),
            "last_updated": now.isoformat(),
        }

    def _metadata(self) -> Dict[str, Any]:
        return {
            "description": "価格転嫁率（中小企業庁・コスト全般）",
            "source": "中小企業庁 価格交渉促進月間フォローアップ調査",
            "source_url": "https://www.chusho.meti.go.jp/keiei/torihiki/follow-up/index.html",
            "frequency": "semi-annual",
            "unit": "%",
            "series": {
                "total": "コスト全般",
                "raw_materials": "原材料費",
                "energy": "エネルギー費",
                "labor": "労務費",
                "zero_pass_through": "全く転嫁できず割合",
            },
            "supply_chain_series": {
                "tier_1": "1次請け",
                "tier_2": "2次請け",
                "tier_3": "3次請け",
                "tier_4_plus": "4次請け以上",
            },
        }

    # ------------------------------------------------------------------
    # キャッシュ管理
    # ------------------------------------------------------------------

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュ読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュ保存"""
        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"[PricePassThrough] Error saving file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュ無効化"""
        try:
            redis_client.delete(self.DATA_CACHE_KEY)
            if DATA_CACHE_FILE.exists():
                DATA_CACHE_FILE.unlink()
            return True
        except Exception:
            return False

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュステータスを取得"""
        cached = redis_client.get(self.DATA_CACHE_KEY)
        return {
            "redis_cache_exists": cached is not None,
            "redis_data_count": len(cached.get("data", [])) if cached else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "last_updated": cached.get("last_updated") if cached else None,
        }


# シングルトン
price_pass_through_rate_service = PricePassThroughRateService()
