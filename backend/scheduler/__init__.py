"""
経済指標スケジューラーパッケージ

発表時刻に合わせて自動的にデータを取得・キャッシュ更新するバックグラウンドスケジューラー
"""

from .indicator_scheduler import indicator_scheduler

__all__ = ["indicator_scheduler"]
