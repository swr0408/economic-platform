"""
Bank of England MPC Voting Service
BOE金融政策委員会（MPC）メンバー投票履歴データを取得

指標:
- 各MPCメンバーの金利投票履歴
- 会合日、決定金利、各メンバーの投票

データソース:
- Bank of England Excel file

発表スケジュール:
- MPC発表日（年8回程度）
- 発表時刻: 12:00 ロンドン時間（20:00-21:00 JST）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from io import BytesIO

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boe_mpc_voting_cache.json"


class BOEMPCVotingService:
    """BOE MPC投票履歴サービス"""

    DATA_CACHE_KEY = "uk:boe_mpc_voting:data"

    # BoE Excel file URL
    EXCEL_URL = "https://www.bankofengland.co.uk/-/media/boe/files/monetary-policy-summary-and-minutes/mpcvoting.xlsx"

    def __init__(self):
        pass

    def get_mpc_voting_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        MPC投票データを取得

        Args:
            force_refresh: 強制更新フラグ

        Returns:
            投票データ
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                cached_list = cached_data.get("data") or []
                latest_meeting = cached_list[-1].get("date") if cached_list else None
                if last_updated_str and not self._should_refresh(last_updated_str, latest_meeting):
                    return {
                        "data": cached_data.get("data", []),
                        "members": cached_data.get("members", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # Excelから取得
        excel_result = self._fetch_excel_data()
        if excel_result:
            next_release = self._get_next_release()

            # 最新データを取得
            latest = None
            if excel_result.get("data"):
                latest_record = excel_result["data"][-1]
                latest = {
                    "date": latest_record.get("date"),
                    "bank_rate": latest_record.get("bank_rate"),
                }

            cache_payload = {
                "data": excel_result.get("data", []),
                "members": excel_result.get("members", []),
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": excel_result.get("data", []),
                "members": excel_result.get("members", []),
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "excel",
                "last_updated": datetime.now(JST).isoformat()
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "members": file_cache.get("members", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "members": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def get_table_data(self, limit: int = 20) -> Dict[str, Any]:
        """
        テーブル表示用のデータを取得

        Args:
            limit: 取得件数

        Returns:
            テーブル用データ
        """
        data = self.get_mpc_voting_data()

        if not data or not data.get("data"):
            return {
                "members": [],
                "data": [],
                "last_updated": None,
                "source": "Bank of England"
            }

        all_data = data["data"]
        recent_data = all_data[-limit:] if len(all_data) > limit else all_data

        # 新しい順に並べ替え
        recent_data = list(reversed(recent_data))

        # テーブル用にフォーマット
        table_data = []
        for record in recent_data:
            row = {
                "date": record["date"],
                "bank_rate": record["bank_rate"],
            }
            # 各メンバーの投票を追加
            for member_name, vote in record.get("member_votes", {}).items():
                row[member_name] = vote
            table_data.append(row)

        return {
            "members": data.get("members", []),
            "data": table_data,
            "next_release": data.get("next_release"),
            "last_updated": data.get("last_updated"),
            "source": "Bank of England"
        }

    def _fetch_excel_data(self) -> Optional[Dict[str, Any]]:
        """
        BOEのExcelファイルからMPC投票データを取得
        """
        try:
            print(f"[BOE MPC Voting] Fetching data from {self.EXCEL_URL}")

            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(self.EXCEL_URL, headers=headers, timeout=30)
            response.raise_for_status()

            df = pd.read_excel(BytesIO(response.content), sheet_name=0, header=None)

            print(f"[BOE MPC Voting] Excel file loaded, shape: {df.shape}")

            # Row 3: メンバー名（columns D-L, indices 3-11）
            member_names = []
            for col_idx in range(3, 12):
                name = df.iloc[3, col_idx]
                if pd.notna(name) and name != "Past members":
                    member_names.append(str(name))

            print(f"[BOE MPC Voting] Found {len(member_names)} current members: {member_names}")

            # データはrow 10から開始
            # Column B (index 1): Date
            # Column C (index 2): Bank Rate
            # Columns D-L (indices 3-11): Member votes
            result = []

            for row_idx in range(10, len(df)):
                date_val = df.iloc[row_idx, 1]
                bank_rate = df.iloc[row_idx, 2]

                if pd.notna(date_val):
                    if isinstance(date_val, str):
                        try:
                            date_obj = pd.to_datetime(date_val)
                        except:
                            continue
                    else:
                        date_obj = date_val

                    date_str = date_obj.strftime('%Y-%m-%d')
                    bank_rate_val = float(bank_rate) if pd.notna(bank_rate) else None

                    member_votes = {}
                    for idx, member_name in enumerate(member_names):
                        col_idx = 3 + idx
                        vote = df.iloc[row_idx, col_idx]
                        if pd.notna(vote):
                            member_votes[member_name] = float(vote)

                    result.append({
                        'date': date_str,
                        'bank_rate': bank_rate_val,
                        'member_votes': member_votes
                    })

            print(f"[BOE MPC Voting] Fetched {len(result)} records")

            return {
                "data": result,
                "members": member_names
            }

        except Exception as e:
            print(f"[BOE MPC Voting] Error fetching Excel data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得"""
        try:
            from services.uk.fmp_next_release_utils import get_next_release_by_pattern
            # BoE Interest Rate Decision を検索（MPC投票も同日）
            return get_next_release_by_pattern("Interest Rate Decision", country="GB")
        except Exception as e:
            print(f"[BOE MPC Voting] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str, latest_meeting_date: Optional[str] = None) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 1) 1日以上経過していたら更新
            if (now - last_updated) > timedelta(days=1):
                return True

            # 2) 発表時刻レース対策（ラグガード）:
            #    直近のBoE金利決定（FMP "Interest Rate Decision" GB）が発生済みなのに
            #    キャッシュの最新会合日がそれより前なら、ソース(BoE Excel)反映待ちとみなして
            #    短時間で再取得する。発表直後（20秒後等）にExcel未反映の旧分をキャッシュして
            #    翌日まで凍結する問題を解消（発表後36hの窓のみ。以後は上記1日TTLが backstop）。
            if latest_meeting_date:
                try:
                    from services.uk.fmp_next_release_utils import _get_last_release_datetime
                    last_release = _get_last_release_datetime("Interest Rate Decision", "GB")
                    if last_release and now >= last_release:
                        age_hours = (now - last_release).total_seconds() / 3600.0
                        if age_hours <= 36 and latest_meeting_date < last_release.strftime("%Y-%m-%d"):
                            print(
                                f"[BOE MPC Voting] release-aware refresh: cached latest meeting "
                                f"{latest_meeting_date} < BoE decision {last_release.date()} → refetch"
                            )
                            return True
                except Exception as e:
                    print(f"[BOE MPC Voting] release-aware check failed: {e}")

            return False
        except Exception as e:
            print(f"[BOE MPC Voting] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[BOE MPC Voting] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[BOE MPC Voting] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "BOE MPC Voting",
            "source": "Bank of England Excel",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "members": cached_data.get("members", []) if cached_data else [],
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
boe_mpc_voting_service = BOEMPCVotingService()
