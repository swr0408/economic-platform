"""
国内民間最終需要（除くソフトウェア・コンピューター設備投資）サービス

BEA NIPA テーブル T20305/T20303（PCE）と T50305/T50303（民間固定投資）から
取得した名目金額と数量指数を用いて、Fisher 数量指数で四半期前期比年率（QoQ SAAR）
を独自に再集計する。

提供する系列:
- ex_sw_pc: 除くソフトウェア・コンピューター設備投資（独自推計）
    PCE + 非住宅構築物 + 住宅 + 設備（PC除く） + IPP（ソフト除く）
- standard: 国内民間最終需要（標準、参考）
    PCE + 非住宅構築物 + 非住宅設備 + 非住宅IPP + 住宅

採用ライン構成（T50305 の LineDescription を使用）:
- PCE: T20305 L1 "Personal consumption expenditures (PCE)"
- Nonresidential structures: T50305 L3 "Structures"  (Private fixed investment > Nonresidential > Structures)
- Equipment ex computers: L12 "Other"(=Other information processing eq) + L13 "Industrial equipment" + L14 "Transportation equipment" + L15 "Other equipment"
- IPP ex software: L18 "Research and development" + L19 "Entertainment, literary, and artistic originals"
- Residential: L20 "Residential" (private fixed investment in residential)

Fisher 数量成長率:
- Laspeyres L_t = Σ[V_prev × (Q_curr/Q_prev)] / Σ[V_prev]
- Paasche   P_t = Σ[V_curr] / Σ[V_curr × (Q_prev/Q_curr)]
- Fisher    F_t = sqrt(L × P)
- QoQ年率 = (F^4 - 1) × 100

キャッシュ方式: last_updated 判定（TTLなし、フォールバック 7日）
更新タイミング: BEA GDP 発表スケジュールに連動
"""
import os
from datetime import datetime
from math import sqrt
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")

BEA_API_BASE = "https://apps.bea.gov/api/data/"

# T50305 / T50303 内の Nonresidential 配下の LineNumber を使用してフィルタリングする。
# LineDescription は重複（例 L3 "Structures" と L21 "Structures"）するため、
# LineNumber ベースで一意に識別する。
EQUIPMENT_EX_COMPUTER_LINE_NUMBERS = [12, 13, 14, 15]  # Other (info proc), Industrial, Transportation, Other equipment
IPP_EX_SOFTWARE_LINE_NUMBERS = [18, 19]  # R&D, Entertainment etc.
NONRESIDENTIAL_STRUCTURES_LINE = 3
NONRESIDENTIAL_EQUIPMENT_TOTAL_LINE = 9
NONRESIDENTIAL_IPP_TOTAL_LINE = 16
RESIDENTIAL_TOTAL_LINE = 20

PCE_TOTAL_LINE = 1  # T20305 L1

# サイレントな BEA テーブル構成変更を検出するための期待値（LineNumber → LineDescription 部分一致）
# 完全一致だと細かな表記揺れに弱いため部分一致でチェックする
EXPECTED_LINE_DESCRIPTIONS = {
    "T20305": {1: "Personal consumption expenditures"},
    "T50305": {
        3: "Structures",
        9: "Equipment",
        12: "Other",  # Other under Information processing
        13: "Industrial equipment",
        14: "Transportation equipment",
        15: "Other equipment",
        16: "Intellectual property products",
        18: "Research and development",
        19: "Entertainment",
        20: "Residential",
    },
}


class DomesticPrivateFinalDemandService:
    """国内民間最終需要（除くSW・PC投資）サービス"""

    CACHE_KEY = "bea:domestic_private_final_demand:ex_sw_pc"
    MAX_CACHE_AGE_DAYS = 7

    def __init__(self):
        self.api_key = os.environ.get("BEA_API_KEY", "")

    def _is_cache_expired(self, cached_data: Dict[str, Any]) -> bool:
        last_updated = cached_data.get("last_updated")
        if not last_updated:
            return True
        try:
            last_dt = datetime.fromisoformat(last_updated)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=JST)
            age = datetime.now(JST) - last_dt
            return age.total_seconds() > self.MAX_CACHE_AGE_DAYS * 86400
        except Exception:
            return True

    def _quarter_to_date_str(self, q: str) -> str:
        try:
            year = int(q[:4])
            qi = int(q[-1])
            month = {1: 1, 2: 4, 3: 7, 4: 10}[qi]
            return f"{year:04d}-{month:02d}-01"
        except Exception:
            return q

    def _date_to_quarter(self, date_str: str) -> str:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            return f"{d.year}Q{(d.month - 1) // 3 + 1}"
        except Exception:
            return date_str

    def fetch_data(
        self,
        start_year: int = 2002,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Returns:
            {
                "data": [
                    {"date": "YYYY-MM-DD", "quarter": "2024Q1",
                     "ex_sw_pc": float, "standard": float},
                    ...
                ],
                "cached": bool,
                "source": str,
                "last_updated": str,
            }
        """
        cached = redis_client.get(self.CACHE_KEY)
        if not force_refresh and cached and not self._is_cache_expired(cached):
            return {
                "data": cached.get("data", []),
                "cached": True,
                "source": "redis",
                "last_updated": cached.get("last_updated"),
            }

        api_data = self._fetch_and_compute(start_year)
        if api_data:
            # 過去キャッシュとマージし、過去に値があった四半期で
            # 今回 None になったものは保全する（BEA の一時的な不整合に備える）
            cached_data = (cached or {}).get("data", [])
            merged = self._merge_with_previous_cache(api_data, cached_data)
            payload = {
                "data": merged,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.CACHE_KEY, payload, expire=0)
            return {
                "data": merged,
                "cached": False,
                "source": "api",
                "last_updated": payload["last_updated"],
            }

        if cached:
            return {
                "data": cached.get("data", []),
                "cached": True,
                "source": "redis_stale",
                "last_updated": cached.get("last_updated"),
            }

        return {
            "data": [],
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _merge_with_previous_cache(
        self,
        new_data: List[Dict[str, Any]],
        cached_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        新データと過去キャッシュをマージし、過去に値があった四半期で今回 None に
        なったものは保全する。BEA の一時的な不整合（例: T50303 更新ラグ）による
        確定値の消失を防ぐ。
        """
        if not cached_data:
            return new_data

        cache_by_date = {item.get("date"): item for item in cached_data if item.get("date")}
        new_dates = {item.get("date") for item in new_data if item.get("date")}
        preserved = 0
        merged: List[Dict[str, Any]] = []

        for new_item in new_data:
            date = new_item.get("date")
            cached_item = cache_by_date.get(date) if date else None
            if cached_item:
                for key in ("ex_sw_pc", "standard"):
                    if new_item.get(key) is None and cached_item.get(key) is not None:
                        new_item[key] = cached_item[key]
                        preserved += 1
            merged.append(new_item)

        # 今回のフェッチで完全に欠落した過去四半期もキャッシュから救済する
        for cached_item in cached_data:
            cached_date = cached_item.get("date")
            if cached_date and cached_date not in new_dates:
                merged.append(cached_item)
                preserved += 1

        merged.sort(key=lambda x: x.get("date") or "")
        if preserved > 0:
            print(f"[dpfd] Preserved {preserved} value(s) from previous cache to prevent data loss")
        return merged

    def _fetch_table(self, table: str, year_range: str) -> Optional[List[Dict[str, Any]]]:
        try:
            params = {
                "UserID": self.api_key,
                "method": "GetData",
                "datasetname": "NIPA",
                "TableName": table,
                "Frequency": "Q",
                "Year": year_range,
                "ResultFormat": "JSON",
            }
            r = requests.get(BEA_API_BASE, params=params, timeout=60)
            r.raise_for_status()
            j = r.json()
            api = j.get("BEAAPI") if isinstance(j, dict) else None
            err = (api or {}).get("Error") or (api or {}).get("Results", {}).get("Error")
            if err:
                print(f"BEA API error for {table}: {err}")
                return None
            return (api or {}).get("Results", {}).get("Data") or []
        except Exception as e:
            print(f"Error fetching BEA table {table}: {e}")
            return None

    def _verify_line_descriptions(self, table: str, rows: List[Dict[str, Any]]) -> None:
        """
        BEA テーブルの LineNumber→LineDescription が想定通りか検証する。

        BEA が将来 NIPA テーブル構成を再編すると、LineNumber が同じでも別の項目を
        指す可能性がある（サイレントに誤集計するリスク）。検出時は警告ログを出す。
        """
        expected = EXPECTED_LINE_DESCRIPTIONS.get(table)
        if not expected:
            return
        seen: Dict[int, str] = {}
        for row in rows:
            try:
                ln = int(row.get("LineNumber"))
            except (TypeError, ValueError):
                continue
            desc = (row.get("LineDescription") or "").strip()
            if ln in expected and ln not in seen:
                seen[ln] = desc
        for ln, expected_substr in expected.items():
            actual = seen.get(ln)
            if actual is None:
                print(f"[dpfd][WARN] {table} L{ln} not found (expected '{expected_substr}')")
                continue
            if expected_substr.lower() not in actual.lower():
                print(
                    f"[dpfd][WARN] {table} L{ln} description mismatch: "
                    f"expected substring '{expected_substr}', got '{actual}'"
                )

    def _index_rows(
        self,
        rows: List[Dict[str, Any]],
        line_numbers: List[int],
    ) -> Dict[Tuple[int, str], float]:
        """Index BEA rows by (LineNumber, TimePeriod) → value."""
        out: Dict[Tuple[int, str], float] = {}
        wanted = set(line_numbers)
        for row in rows:
            try:
                ln = int(row.get("LineNumber"))
            except (TypeError, ValueError):
                continue
            if ln not in wanted:
                continue
            tp = row.get("TimePeriod")
            val = row.get("DataValue")
            if not tp or val in (None, "", ".", "NaN", "(NA)"):
                continue
            try:
                num = float(str(val).replace(",", ""))
            except ValueError:
                continue
            out[(ln, tp)] = num
        return out

    def _fetch_and_compute(self, start_year: int) -> Optional[List[Dict[str, Any]]]:
        if not self.api_key:
            print("BEA_API_KEY not set")
            return None

        current_year = datetime.now().year
        year_range = ",".join(str(y) for y in range(start_year, current_year + 2))

        # 4テーブルを取得 (PCE/PFI x 名目/数量)
        pce_nom = self._fetch_table("T20305", year_range)
        pce_qty = self._fetch_table("T20303", year_range)
        pfi_nom = self._fetch_table("T50305", year_range)
        pfi_qty = self._fetch_table("T50303", year_range)

        if not (pce_nom and pce_qty and pfi_nom and pfi_qty):
            print("Failed to fetch one or more BEA tables")
            return None

        # BEA テーブル構成の整合性チェック（サイレントな仕様変更を検出）
        self._verify_line_descriptions("T20305", pce_nom)
        self._verify_line_descriptions("T50305", pfi_nom)

        pce_nom_idx = self._index_rows(pce_nom, [PCE_TOTAL_LINE])
        pce_qty_idx = self._index_rows(pce_qty, [PCE_TOTAL_LINE])

        # 除くSW・PC 用構成: 構造物(L3) + Eq詳細(L12-15) + IPP詳細(L18,L19) + 住宅(L20)
        ex_lines = [
            NONRESIDENTIAL_STRUCTURES_LINE,
            *EQUIPMENT_EX_COMPUTER_LINE_NUMBERS,
            *IPP_EX_SOFTWARE_LINE_NUMBERS,
            RESIDENTIAL_TOTAL_LINE,
        ]
        # 標準版用構成: 構造物(L3) + Eq全部(L9) + IPP全部(L16) + 住宅(L20)
        std_lines = [
            NONRESIDENTIAL_STRUCTURES_LINE,
            NONRESIDENTIAL_EQUIPMENT_TOTAL_LINE,
            NONRESIDENTIAL_IPP_TOTAL_LINE,
            RESIDENTIAL_TOTAL_LINE,
        ]
        all_pfi_lines = sorted(set(ex_lines + std_lines))

        pfi_nom_idx = self._index_rows(pfi_nom, all_pfi_lines)
        pfi_qty_idx = self._index_rows(pfi_qty, all_pfi_lines)

        # 取得した全 TimePeriod の和集合を使う（PCE と PFI のリリースラグに頑強）
        all_tps = set()
        all_tps.update(tp for (_, tp) in pce_nom_idx.keys())
        all_tps.update(tp for (_, tp) in pfi_nom_idx.keys())
        periods = sorted(tp for tp in all_tps if int(str(tp)[:4]) >= start_year)

        # 構成要素ごとに (V, Q) 系列を構築
        # キー: 識別子。値: dict {period: (V, Q)}
        def build_component_series(component_id: str, source: str, line: int) -> Dict[str, Tuple[Optional[float], Optional[float]]]:
            series: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
            for tp in periods:
                if source == "pce":
                    v = pce_nom_idx.get((line, tp))
                    q = pce_qty_idx.get((line, tp))
                else:
                    v = pfi_nom_idx.get((line, tp))
                    q = pfi_qty_idx.get((line, tp))
                series[tp] = (v, q)
            return series

        ex_components: Dict[str, Dict[str, Tuple[Optional[float], Optional[float]]]] = {}
        ex_components["pce"] = build_component_series("pce", "pce", PCE_TOTAL_LINE)
        for ln in ex_lines:
            ex_components[f"pfi_{ln}"] = build_component_series(f"pfi_{ln}", "pfi", ln)

        std_components: Dict[str, Dict[str, Tuple[Optional[float], Optional[float]]]] = {}
        std_components["pce"] = build_component_series("pce", "pce", PCE_TOTAL_LINE)
        for ln in std_lines:
            std_components[f"pfi_{ln}"] = build_component_series(f"pfi_{ln}", "pfi", ln)

        ex_growth = self._fisher_qoq_saar(ex_components, periods)
        std_growth = self._fisher_qoq_saar(std_components, periods)

        # 結果を統合
        points: List[Dict[str, Any]] = []
        for tp in periods:
            ex_val = ex_growth.get(tp)
            std_val = std_growth.get(tp)
            if ex_val is None and std_val is None:
                continue
            date_str = self._quarter_to_date_str(tp)
            points.append({
                "date": date_str,
                "quarter": self._date_to_quarter(date_str),
                "ex_sw_pc": round(ex_val, 2) if ex_val is not None else None,
                "standard": round(std_val, 2) if std_val is not None else None,
            })

        print(f"Domestic private final demand: computed {len(points)} quarters")
        return points

    def _fisher_qoq_saar(
        self,
        components: Dict[str, Dict[str, Tuple[Optional[float], Optional[float]]]],
        periods: List[str],
    ) -> Dict[str, Optional[float]]:
        """各四半期について Fisher 数量成長率を計算し、QoQ 年率（%）を返す.

        全構成要素が揃っている期のみ採用する（部分集合での Fisher は系列の連続性を
        壊し、偏った成長率を返してしまうため）。揃わない場合は None を返し、上位で
        過去キャッシュから保全する設計にしている。
        """
        expected_count = len(components)
        result: Dict[str, Optional[float]] = {periods[0]: None} if periods else {}
        for i in range(1, len(periods)):
            prev_tp = periods[i - 1]
            curr_tp = periods[i]

            laspeyres_num = 0.0
            laspeyres_den = 0.0
            paasche_num = 0.0
            paasche_den = 0.0
            valid_count = 0

            for comp_series in components.values():
                v_prev, q_prev = comp_series.get(prev_tp, (None, None))
                v_curr, q_curr = comp_series.get(curr_tp, (None, None))
                if (v_prev is None or v_curr is None or q_prev is None or q_curr is None
                        or q_prev == 0 or q_curr == 0):
                    continue
                laspeyres_num += v_prev * (q_curr / q_prev)
                laspeyres_den += v_prev
                paasche_num += v_curr
                paasche_den += v_curr * (q_prev / q_curr)
                valid_count += 1

            # 構成要素が1つでも欠けていれば None（部分バスケットの Fisher は採用しない）
            if valid_count < expected_count or laspeyres_den <= 0 or paasche_den <= 0:
                result[curr_tp] = None
                continue

            laspeyres = laspeyres_num / laspeyres_den
            paasche = paasche_num / paasche_den
            if laspeyres <= 0 or paasche <= 0:
                result[curr_tp] = None
                continue
            fisher = sqrt(laspeyres * paasche)
            qoq_saar = (fisher ** 4 - 1.0) * 100.0
            result[curr_tp] = qoq_saar
        return result

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        return self.fetch_data(force_refresh=force_refresh)

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if exists else -1
        cached = redis_client.get(self.CACHE_KEY) if exists else None
        return {
            "cache_key": self.CACHE_KEY,
            "exists": exists,
            "ttl_seconds": ttl,
            "last_updated": cached.get("last_updated") if cached else None,
            "record_count": len(cached.get("data", [])) if cached else 0,
        }


domestic_private_final_demand_service = DomesticPrivateFinalDemandService()
