# -*- coding: utf-8 -*-
"""
相関・先行性レポート バッチ生成 CLI (master 限定レポート用・オフライン実行)。

    python -m backend.scripts.correlation_analysis.run --as-of 2026-06 [--scope full|quick]

- 外部API/スクレイピングは一切行わない純ローカルCPU処理。
- 既存のデータ更新スケジューラとは独立。CPU競合を避けるためオフピーク実行推奨。
- 出力: backend/data/reports/correlation/<as_of>/ (manifest.json / sections / matrices)

四半期に1回程度の手動再生成を想定 (相関は構造安定のため日次更新は不要)。
pandas / numpy / scipy / statsmodels が必要 (バッチ専用依存・配信APIは未使用)。
"""
import argparse
import sys

try:
    from backend.services.correlation import report_builder
except ImportError:  # 直接実行フォールバック
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
    from backend.services.correlation import report_builder


def main():
    ap = argparse.ArgumentParser(description="相関・先行性レポート生成")
    ap.add_argument("--as-of", required=True, help="スナップショット識別子 (例: 2026-06)")
    ap.add_argument("--scope", default="full", choices=["full", "quick"],
                    help="full=全国+全銘柄 / quick=米国のみ(検証用)")
    args = ap.parse_args()
    report_builder.build(args.as_of, scope=args.scope)


if __name__ == "__main__":
    main()
