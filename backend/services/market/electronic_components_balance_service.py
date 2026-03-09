"""
電子部品・デバイス工業 出荷在庫バランス サービス

計算式:
  Balance = (出荷指数 前年比) - (在庫指数 前年比)
  Balance_3MA = 3ヶ月移動平均

データソース:
  - 経済産業省 鉱工業指数 (IIP)
    2018年1月～: https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_gom1j.xlsx
    接続指数(～2022年12月): https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_sgo1j.xlsx
  - 日経平均: yfinance (^N225) 月足

更新スケジュール: 日次（JST 7:00）
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "electronic_components_balance_cache.json"

# Redis
DATA_CACHE_KEY = "market:electronic_components_balance:data"

# METI IIP Excel URLs
METI_CURRENT_URL = "https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_gom1j.xlsx"
METI_HISTORICAL_URL = "https://www.meti.go.jp/statistics/tyo/iip/xls/b2020_sgo1j.xlsx"

# ローカルExcelファイル（METI接続不可時のフォールバック）
EXCEL_DIR = Path(__file__).parent.parent.parent / "data" / "excel"
LOCAL_CURRENT_FILE = EXCEL_DIR / "b2020_gom1j.xlsx"
LOCAL_HISTORICAL_FILE = EXCEL_DIR / "b2020_sgo1j.xlsx"

# ターゲット業種コード
TARGET_INDUSTRY_CODE = "1105000000"  # 電子部品・デバイス工業
TARGET_INDUSTRY_NAME = "電子部品・デバイス工業"

# HTTP headers (METI requires browser-like User-Agent)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


class ElectronicComponentsBalanceService:
    """電子部品・デバイス工業 出荷在庫バランス サービス"""

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
        """出荷在庫バランスデータを取得"""
        if not force_refresh and not self._should_refresh():
            cached = self._load_from_redis()
            if cached and cached.get("data"):
                return cached

        try:
            data = self._build_data()
            if data and data.get("data"):
                self._save_to_cache(data)
                return data
        except Exception as e:
            logger.error(f"[ElecBalance] Build error: {e}")
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
            "metadata": {"source": "Electronic Components Balance"},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _download_excel(self, url: str, local_path: Path) -> Optional[bytes]:
        """Excelファイルをダウンロード（失敗時はローカルファイルにフォールバック）"""
        import requests

        # まずオンラインから取得を試みる
        try:
            resp = requests.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            logger.info(
                f"[ElecBalance] Downloaded {url.split('/')[-1]}: {len(resp.content)} bytes"
            )
            # ローカルにも保存（次回のフォールバック用）
            try:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(resp.content)
            except Exception:
                pass
            return resp.content
        except Exception as e:
            logger.warning(f"[ElecBalance] Download failed ({url}): {e}")

        # ローカルファイルにフォールバック
        try:
            if local_path.exists():
                with open(local_path, "rb") as f:
                    content = f.read()
                logger.info(
                    f"[ElecBalance] Using local file {local_path.name}: {len(content)} bytes"
                )
                return content
        except Exception as e:
            logger.error(f"[ElecBalance] Local file read error: {e}")

        return None

    def _parse_date_value(self, date_val) -> Optional[str]:
        """日付値をYYYY-MM形式に変換。速報値(p)プレフィックスも処理"""
        import pandas as pd

        if pd.isna(date_val):
            return None

        date_str = str(date_val).strip()

        # 速報値プレフィックス "p " を除去
        if date_str.startswith("p "):
            date_str = date_str[2:].strip()

        try:
            # float型の場合 (201801.0)
            if isinstance(date_val, float) and not pd.isna(date_val):
                date_int = int(date_val)
                year = date_int // 100
                month = date_int % 100
            elif isinstance(date_val, int):
                year = date_val // 100
                month = date_val % 100
            else:
                # 文字列の場合 ("p 202601" → "202601")
                clean = date_str.replace(".", "").strip()
                if len(clean) == 6:
                    year = int(clean[:4])
                    month = int(clean[4:6])
                elif len(clean) >= 6:
                    # "201801.0" → float → int
                    try:
                        numeric = float(clean)
                        date_int = int(numeric)
                        year = date_int // 100
                        month = date_int % 100
                    except ValueError:
                        return None
                else:
                    return None

            if 1900 <= year <= 2100 and 1 <= month <= 12:
                return f"{year:04d}-{month:02d}"
        except (ValueError, IndexError):
            pass

        return None

    def _extract_current_iip_data(
        self, excel_content: bytes
    ) -> Optional[Dict[str, Dict[str, float]]]:
        """現行Excelから出荷・在庫の月次指数を抽出（2018年1月～）

        ファイル構造: 業種が行、日付が列（標準配置）
        シート: [利用上の注意, 生産, 出荷, 在庫, 在庫率]

        Returns:
            {"shipment": {"2018-01": 96.1, ...}, "inventory": {"2018-01": 101.4, ...}}
        """
        import io

        import pandas as pd

        try:
            xls = pd.ExcelFile(io.BytesIO(excel_content))
            sheets = xls.sheet_names

            if len(sheets) < 4:
                logger.error(f"[ElecBalance] Current: Unexpected sheet count: {sheets}")
                return None

            result: Dict[str, Dict[str, float]] = {}

            # 出荷 = sheet index 2, 在庫 = sheet index 3
            for si, label in [(2, "shipment"), (3, "inventory")]:
                df = pd.read_excel(
                    io.BytesIO(excel_content),
                    sheet_name=sheets[si],
                    header=None,
                )

                # 日付行を取得 (Row 2)
                date_row = df.iloc[2]

                # ターゲット行を検索
                target_row_idx = self._find_target_row(df)
                if target_row_idx is None:
                    logger.error(
                        f"[ElecBalance] Target row not found in sheet {sheets[si]}"
                    )
                    return None

                data_row = df.iloc[target_row_idx]
                monthly_data: Dict[str, float] = {}

                for col in range(3, df.shape[1]):
                    date_key = self._parse_date_value(date_row.iloc[col])
                    if date_key is None:
                        continue

                    data_val = data_row.iloc[col]
                    if pd.isna(data_val):
                        continue

                    try:
                        val = float(data_val)
                        if val > 0:
                            monthly_data[date_key] = val
                    except (ValueError, TypeError):
                        continue

                result[label] = monthly_data
                logger.info(
                    f"[ElecBalance] Current {label}: {len(monthly_data)} months "
                    f"({min(monthly_data.keys()) if monthly_data else 'N/A'} to "
                    f"{max(monthly_data.keys()) if monthly_data else 'N/A'})"
                )

            return result

        except Exception as e:
            logger.error(f"[ElecBalance] Current Excel parse error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_historical_iip_data(
        self, excel_content: bytes
    ) -> Optional[Dict[str, Dict[str, float]]]:
        """接続指数Excelから出荷・在庫の月次指数を抽出（～2022年12月）

        ファイル構造: 日付が行、業種が列（転置配置）
        シート: [生産付加価値, 出荷, 在庫, 在庫率]
        Row 0: タイトル
        Row 1: 業種コード（Col 1～）
        Row 2: 業種名（Col 1～）
        Row 3: 接続指数（変換係数）（Col 0=ラベル, Col 1～=値）
        Row 4～: 月次データ（Col 0=長い日付コード, Col 1=YYYYMM, Col 2～=データ）

        ターゲット: Col 49 = 電子部品・デバイス工業 (code 1105000000)

        Returns:
            {"shipment": {"1998-01": 96.1, ...}, "inventory": {"1998-01": 101.4, ...}}
        """
        import io

        import pandas as pd

        try:
            xls = pd.ExcelFile(io.BytesIO(excel_content))
            sheets = xls.sheet_names

            if len(sheets) < 3:
                logger.error(f"[ElecBalance] Historical: Unexpected sheet count: {sheets}")
                return None

            result: Dict[str, Dict[str, float]] = {}

            # 出荷 = sheet index 1, 在庫 = sheet index 2
            for si, label in [(1, "shipment"), (2, "inventory")]:
                df = pd.read_excel(
                    io.BytesIO(excel_content),
                    sheet_name=sheets[si],
                    header=None,
                )

                # ターゲット列を検索（Row 1 = 業種コード）
                target_col = None
                for col in range(2, df.shape[1]):
                    code = df.iloc[1, col]
                    if pd.notna(code) and str(code).strip() == TARGET_INDUSTRY_CODE:
                        target_col = col
                        break

                if target_col is None:
                    logger.error(
                        f"[ElecBalance] Historical: Target column not found in {sheets[si]}"
                    )
                    return None

                # 接続指数（変換係数）を取得 (Row 3)
                connection_index = df.iloc[3, target_col]
                if pd.notna(connection_index):
                    try:
                        connection_factor = float(connection_index)
                    except (ValueError, TypeError):
                        connection_factor = 1.0
                else:
                    connection_factor = 1.0

                logger.info(
                    f"[ElecBalance] Historical {label}: col={target_col}, "
                    f"connection factor = {connection_factor}"
                )

                # Row 4以降が月次データ、Col 1 = YYYYMM (integer)
                monthly_data: Dict[str, float] = {}
                for row_idx in range(4, df.shape[0]):
                    # Col 1 = YYYYMM 形式の整数
                    date_val = df.iloc[row_idx, 1]
                    date_key = self._parse_date_value(date_val)
                    if date_key is None:
                        continue

                    data_val = df.iloc[row_idx, target_col]
                    if pd.isna(data_val):
                        continue

                    # "-" は欠損値
                    if isinstance(data_val, str) and data_val.strip() == "-":
                        continue

                    try:
                        val = float(data_val)
                        if val > 0:
                            # 接続指数で変換して2020基準に合わせる
                            monthly_data[date_key] = round(val * connection_factor, 4)
                    except (ValueError, TypeError):
                        continue

                result[label] = monthly_data
                logger.info(
                    f"[ElecBalance] Historical {label}: {len(monthly_data)} months "
                    f"({min(monthly_data.keys()) if monthly_data else 'N/A'} to "
                    f"{max(monthly_data.keys()) if monthly_data else 'N/A'})"
                )

            return result

        except Exception as e:
            logger.error(f"[ElecBalance] Historical Excel parse error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _find_target_row(self, df) -> Optional[int]:
        """DataFrameからターゲット業種の行を検索"""
        import pandas as pd

        # 業種名で検索
        for row_idx in range(3, df.shape[0]):
            name = df.iloc[row_idx, 1]
            if pd.notna(name) and isinstance(name, str):
                if TARGET_INDUSTRY_NAME in name:
                    return row_idx

        # コードで検索
        for row_idx in range(3, df.shape[0]):
            code = df.iloc[row_idx, 0]
            if pd.notna(code) and str(code).strip() == TARGET_INDUSTRY_CODE:
                return row_idx

        return None

    def _get_nikkei_monthly(self) -> Dict[str, float]:
        """yfinanceから日経平均月足終値を取得"""
        import yfinance as yf

        try:
            ticker = yf.Ticker("^N225")
            end_dt = datetime.now(JST) + timedelta(days=5)
            # 接続指数は1998年開始なので、YoY計算のために1997年から取得
            hist = ticker.history(
                start="1997-01-01",
                end=end_dt.strftime("%Y-%m-%d"),
                interval="1mo",
            )

            if hist.empty:
                logger.warning("[ElecBalance] No yfinance data for ^N225")
                return {}

            result: Dict[str, float] = {}
            for idx, row in hist.iterrows():
                date_str = f"{idx.year:04d}-{idx.month:02d}"
                result[date_str] = round(float(row["Close"]), 0)

            logger.info(f"[ElecBalance] Nikkei monthly: {len(result)} months")
            return result

        except Exception as e:
            logger.error(f"[ElecBalance] yfinance error: {e}")
            return {}

    def _detect_preliminary_months(self, excel_content: bytes) -> Set[str]:
        """速報値（p プレフィックス）の月を検出"""
        import io

        import pandas as pd

        preliminary: Set[str] = set()
        try:
            xls = pd.ExcelFile(io.BytesIO(excel_content))
            sheets = xls.sheet_names
            if len(sheets) < 4:
                return preliminary

            # 出荷シートの日付行をチェック
            df = pd.read_excel(
                io.BytesIO(excel_content),
                sheet_name=sheets[2],
                header=None,
            )
            date_row = df.iloc[2]
            for col in range(3, df.shape[1]):
                val = date_row.iloc[col]
                if pd.notna(val):
                    val_str = str(val).strip()
                    if val_str.startswith("p "):
                        date_key = self._parse_date_value(val)
                        if date_key:
                            preliminary.add(date_key)
        except Exception:
            pass

        return preliminary

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """データを構築"""
        logger.info("[ElecBalance] Building data...")

        # 1. 現行データ取得
        current_content = self._download_excel(METI_CURRENT_URL, LOCAL_CURRENT_FILE)
        if not current_content:
            return None

        current_data = self._extract_current_iip_data(current_content)
        if not current_data:
            return None

        # 速報値の月を検出
        preliminary_months = self._detect_preliminary_months(current_content)
        if preliminary_months:
            logger.info(f"[ElecBalance] Preliminary months: {preliminary_months}")

        # 2. 接続指数（歴史データ）取得
        historical_content = self._download_excel(METI_HISTORICAL_URL, LOCAL_HISTORICAL_FILE)
        historical_data = None
        if historical_content:
            historical_data = self._extract_historical_iip_data(historical_content)

        # 3. データをマージ（現行データが優先）
        shipment: Dict[str, float] = {}
        inventory: Dict[str, float] = {}

        if historical_data:
            shipment.update(historical_data.get("shipment", {}))
            inventory.update(historical_data.get("inventory", {}))

        # 現行データで上書き（重複月は現行が優先）
        shipment.update(current_data["shipment"])
        inventory.update(current_data["inventory"])

        logger.info(
            f"[ElecBalance] Merged shipment: {len(shipment)} months "
            f"({min(shipment.keys())} to {max(shipment.keys())})"
        )
        logger.info(
            f"[ElecBalance] Merged inventory: {len(inventory)} months "
            f"({min(inventory.keys())} to {max(inventory.keys())})"
        )

        # 4. 前年比バランスを計算
        all_months = sorted(set(shipment.keys()) & set(inventory.keys()))
        balance_map: Dict[str, float] = {}

        for month in all_months:
            year = int(month[:4])
            mon = int(month[5:7])
            prev_month_key = f"{year - 1:04d}-{mon:02d}"

            if prev_month_key not in shipment or prev_month_key not in inventory:
                continue

            if shipment[prev_month_key] == 0 or inventory[prev_month_key] == 0:
                continue

            ship_yoy = shipment[month] / shipment[prev_month_key] - 1
            inv_yoy = inventory[month] / inventory[prev_month_key] - 1
            balance_map[month] = round(ship_yoy - inv_yoy, 4)

        # 5. 3ヶ月移動平均
        sorted_months = sorted(balance_map.keys())
        balance_3ma_map: Dict[str, float] = {}
        for i, month in enumerate(sorted_months):
            if i < 2:
                continue
            window = [balance_map[sorted_months[j]] for j in range(i - 2, i + 1)]
            balance_3ma_map[month] = round(sum(window) / 3.0, 4)

        # 6. 日経平均月足データ
        nikkei = self._get_nikkei_monthly()

        # 7. 日経平均前年比
        nikkei_yoy_map: Dict[str, float] = {}
        for month, price in nikkei.items():
            year = int(month[:4])
            mon = int(month[5:7])
            prev_key = f"{year - 1:04d}-{mon:02d}"
            if prev_key in nikkei and nikkei[prev_key] > 0:
                yoy = (price / nikkei[prev_key] - 1) * 100
                nikkei_yoy_map[month] = round(yoy, 2)

        # 8. 全データをマージ
        all_data_months = sorted(balance_map.keys())
        result_data: List[Dict[str, Any]] = []

        for month in all_data_months:
            is_preliminary = month in preliminary_months
            item: Dict[str, Any] = {
                "date": f"{month}-01",
                "balance": round(balance_map[month] * 100, 2),  # % 表示
                "balance_3ma": (
                    round(balance_3ma_map[month] * 100, 2)
                    if month in balance_3ma_map
                    else None
                ),
                "nikkei_yoy": nikkei_yoy_map.get(month),
                "nikkei": nikkei.get(month),
                "preliminary": is_preliminary,
            }
            result_data.append(item)

        # バランスデータにない最新月の日経平均データも追加
        balance_months_set = set(all_data_months)
        for month in sorted(nikkei.keys()):
            if month not in balance_months_set and all_data_months and month > min(all_data_months):
                item = {
                    "date": f"{month}-01",
                    "balance": None,
                    "balance_3ma": None,
                    "nikkei_yoy": nikkei_yoy_map.get(month),
                    "nikkei": nikkei.get(month),
                    "preliminary": False,
                }
                result_data.append(item)

        result_data.sort(key=lambda x: x["date"])

        if not result_data:
            return None

        # latestはバランスデータがある最新月
        latest_with_balance = [d for d in result_data if d.get("balance") is not None]
        latest = latest_with_balance[-1].copy() if latest_with_balance else result_data[-1].copy()
        now_str = datetime.now(JST).isoformat()

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "source": "METI IIP / yfinance",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"],
                "end_date": result_data[-1]["date"],
                "balance_count": len(balance_map),
                "balance_start": all_data_months[0] if all_data_months else None,
                "balance_latest": (
                    latest_with_balance[-1]["date"] if latest_with_balance else None
                ),
                "nikkei_latest": (
                    max(m for m in nikkei.keys()) if nikkei else None
                ),
                "preliminary_months": sorted(preliminary_months),
            },
            "cached": False,
            "source": "model",
            "last_updated": now_str,
        }

    def _save_to_cache(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(DATA_CACHE_KEY, data, expire=86400)
        except Exception as e:
            logger.error(f"[ElecBalance] Redis save error: {e}")

        try:
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"[ElecBalance] File save error: {e}")

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(DATA_CACHE_KEY)
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception as e:
            logger.error(f"[ElecBalance] Redis load error: {e}")
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
            logger.error(f"[ElecBalance] File load error: {e}")
        return None


# シングルトン
electronic_components_balance_service = ElectronicComponentsBalanceService()
