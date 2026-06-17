"""
中国 GDP成長率(YoY/QoQ) ・ 鉱工業生産(YoY) の履歴CSVを nbs_monthly_data へインポート

対象CSV（FMPカレンダー エクスポート形式、ヘッダー無し）:
  列0: 発表日 + 対象期間ラベル  例 "2026年6月16日 (5月)" / "2026年4月16日 (Q1)"
  列1: 時刻
  列2: 実績値(actual)  例 "4.50%"   ← これを採用
  列3: 予測値(estimate)
  列4: 前回値(previous)

  - 中国鉱工業生産.csv → cn_industrial_production_yoy（月次, ラベル "(N月)"）
  - 中国GDP前年比.csv   → cn_gdp_yoy（四半期, ラベル "(Qn)" / 初期はラベル無し）
  - 中国GDP前期比.csv   → cn_gdp_qoq（四半期, 同上）

対象期間→日付は nbs_monthly_data の既存規約 YYYY-MM-01 に正規化
（四半期は四半期末月 Q1→03 / Q2→06 / Q3→09 / Q4→12 の1日）。
対象月が発表月より後＝前年データ（12月分/Q4が翌年1月発表）として年を補正。
ラベル無しの四半期行は「発表日の直前に終了した四半期」から導出。

冪等（ON CONFLICT UPDATE）。source="csv" で投入するため関連サービス／
ダッシュボードキャッシュも自動無効化される（nbs_db_utils 側）。
"""
import sys
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
env_path = project_root.parent / ".env"
load_dotenv(env_path)

_QUARTER_END_MONTH = {1: 3, 2: 6, 3: 9, 4: 12}

RE_RELEASE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
RE_MONTH_LABEL = re.compile(r"\((\d{1,2})月\)")
RE_QUARTER_LABEL = re.compile(r"\(Q([1-4])\)")


def _quarter_end_before(release_month: int) -> int:
    """発表月の直前に終了した四半期末月（3/6/9/12）を返す。

    1月発表→12（前年Q4）, 4月→3, 7月→6, 10月→9。
    """
    for q_end in (12, 9, 6, 3):
        if q_end < release_month:
            return q_end
    return 12  # release_month<=3 → 前年12月（年は呼び出し側で補正）


def _period_date(col0: str, quarterly: bool) -> Optional[str]:
    """列0（発表日＋期間ラベル）からデータ対象日付 YYYY-MM-01 を解析"""
    mrel = RE_RELEASE.search(col0)
    if not mrel:
        return None
    rel_year, rel_month = int(mrel.group(1)), int(mrel.group(2))

    period_month: Optional[int] = None
    if quarterly:
        mq = RE_QUARTER_LABEL.search(col0)
        if mq:
            period_month = _QUARTER_END_MONTH[int(mq.group(1))]
        else:
            # ラベル無し → 発表日の直前に終了した四半期
            period_month = _quarter_end_before(rel_month)
    else:
        mm = RE_MONTH_LABEL.search(col0)
        if mm:
            period_month = int(mm.group(1))
        else:
            # ラベル無し月次 → 発表月の前月
            period_month = rel_month - 1 if rel_month > 1 else 12

    if not period_month or not (1 <= period_month <= 12):
        return None

    year = rel_year
    if period_month > rel_month:
        year -= 1
    return f"{year}-{period_month:02d}-01"


def _parse_value(col2: str) -> Optional[float]:
    s = (col2 or "").strip().replace("%", "")
    if not s:
        return None
    try:
        return round(float(s), 1)
    except ValueError:
        return None


def parse_file(file_path: Path, quarterly: bool) -> Dict[str, float]:
    """CSVを解析して {date_str: value} を返す（同一日付は新しい行=下方を優先）"""
    result: Dict[str, float] = {}
    with open(file_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 3:
                continue
            date_str = _period_date(parts[0], quarterly)
            if not date_str:
                continue
            value = _parse_value(parts[2])
            if value is None:
                continue
            result[date_str] = value
    return result


FILES: Tuple[Tuple[str, str, bool], ...] = (
    ("中国鉱工業生産.csv", "cn_industrial_production_yoy", False),
    ("中国GDP前年比.csv", "cn_gdp_yoy", True),
    ("中国GDP前期比.csv", "cn_gdp_qoq", True),
)
# 失業率(total+若年16-24)は cn_unemployment_rate_service が
# data/csv_import/"ChinaUnemployment Rate.csv"(NBS公式 転置ワイド)を
# mtime自動検知で取り込むため、ここでは扱わない。


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Import China GDP/Industrial Production history CSV to nbs_monthly_data"
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't insert")
    parser.add_argument("--samples", type=int, default=3, help="Show N sample rows per file")
    args = parser.parse_args()

    csv_dir = Path(__file__).parent.parent / "data" / "csv_import"
    total = 0

    for filename, db_indicator, quarterly in FILES:
        fp = csv_dir / filename
        print(f"\n{'='*60}\n{filename} → {db_indicator}\n{'='*60}")
        if not fp.exists():
            print(f"  [SKIP] not found: {fp}")
            continue

        data = parse_file(fp, quarterly)
        if not data:
            print("  0 records parsed")
            continue

        keys = sorted(data.keys())
        print(f"  parsed {len(data)} records ({keys[0]} ~ {keys[-1]})")
        head = keys[: args.samples]
        tail = keys[-args.samples:]
        for k in head:
            print(f"    head {k} = {data[k]}")
        for k in tail:
            print(f"    tail {k} = {data[k]}")

        if args.dry_run:
            continue

        from services.china.nbs_db_utils import upsert_nbs_data
        count = upsert_nbs_data(db_indicator, data, source="csv")
        total += count
        print(f"  → DB upserted: {count}")

    print(f"\n{'='*60}\nTOTAL UPSERTED: {total}"
          + ("  (DRY RUN)" if args.dry_run else "") + f"\n{'='*60}")


if __name__ == "__main__":
    main()
