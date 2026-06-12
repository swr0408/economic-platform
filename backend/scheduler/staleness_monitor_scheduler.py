"""
キャッシュ鮮度モニタ スケジューラー (取りこぼし検知ガード)

毎日 10:30 JST に全キャッシュを走査し、期待リリース間隔より大幅に遅れている
ものを WARNING ログに出力する。ソース機構の劣化による silent failure を
自動で可視化するための見張り役。

注意: scan は同期 (ファイル I/O) なので asyncio.to_thread で実行し、
イベントループをブロックしない (過去の event-loop block 事象への対策)。
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


class StalenessMonitorScheduler:
    """キャッシュ鮮度モニタ スケジューラー"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=JST)
        self._last_result: Dict[str, Any] = {}

    def _run_scan(self) -> Dict[str, Any]:
        try:
            from backend.services.monitoring.staleness_monitor import log_stale_summary
        except ImportError:
            from services.monitoring.staleness_monitor import log_stale_summary
        result = log_stale_summary()
        # Discord 通知 (STUCK があるときのみ)。同期 I/O だが本メソッドは
        # asyncio.to_thread 内で実行されるためブロック問題なし。
        try:
            self._post_to_discord(result)
        except Exception as e:
            logger.error(f"[StalenessMonitor] Discord notify error: {e}")
        return result

    # 通知対象とする overdue 下限 (これ未満は通常リリースラグの可能性が高く除外)。
    # env STALENESS_ALERT_MIN_OVERDUE で調整可。
    _DEFAULT_ALERT_MIN_OVERDUE = 4.0

    def send_test_notification(self) -> dict:
        """セットアップ確認用: Webhook へテストメッセージを送る (state を変更しない)。

        .env に DISCORD_STALENESS_WEBHOOK_URL (または DISCORD_WEBHOOK_URL) を設定後、
        `python -c "from scheduler.staleness_monitor_scheduler import staleness_monitor_scheduler as s; print(s.send_test_notification())"`
        で接続確認できる。
        """
        import os
        import requests
        webhook = (
            os.environ.get("DISCORD_STALENESS_WEBHOOK_URL")
            or os.environ.get("DISCORD_WEBHOOK_URL")
        )
        if not webhook:
            return {"ok": False, "reason": "DISCORD_STALENESS_WEBHOOK_URL / DISCORD_WEBHOOK_URL 未設定"}
        try:
            resp = requests.post(webhook, json={
                "username": "Staleness Monitor",
                "embeds": [{
                    "title": "✅ 鮮度モニタ通知テスト",
                    "description": "このチャンネルに鮮度アラートが届きます。\n"
                                   "新たに凍結した指標が出たときのみ自動通知します。",
                    "color": 0x2ECC71,
                }],
            }, timeout=15)
            return {"ok": resp.status_code in (200, 204), "status": resp.status_code}
        except Exception as e:
            return {"ok": False, "reason": str(e)}

    def _alert_state_path(self):
        from pathlib import Path
        return Path(__file__).resolve().parents[1] / "data" / "cache" / "_staleness_alert_state.json"

    def _post_to_discord(self, result: Dict[str, Any]) -> None:
        """鮮度スキャン結果を Discord Webhook へ通知する。

        ノイズ回避のため「前回スキャンに無く今回 STUCK になった指標 (= 新たに凍結)」
        だけを通知する。定常状態 (同じ指標が凍結し続けている) では通知しない。
        初回 (state ファイル無し) はベースラインを記録するのみで通知しない。
        併せて、前回 STUCK だが今回解消した指標 (= 復旧) も知らせる。

        Webhook URL は専用 `DISCORD_STALENESS_WEBHOOK_URL` を優先し、
        未設定なら既存 `DISCORD_WEBHOOK_URL` にフォールバック。両方無ければ何もしない。
        通知対象は overdue >= STALENESS_ALERT_MIN_OVERDUE (既定 4.0) の STUCK に限定。
        """
        import os
        import json
        import requests

        webhook = (
            os.environ.get("DISCORD_STALENESS_WEBHOOK_URL")
            or os.environ.get("DISCORD_WEBHOOK_URL")
        )
        if not webhook:
            return

        try:
            min_overdue = float(os.environ.get("STALENESS_ALERT_MIN_OVERDUE",
                                               self._DEFAULT_ALERT_MIN_OVERDUE))
        except ValueError:
            min_overdue = self._DEFAULT_ALERT_MIN_OVERDUE

        items = result.get("items", []) or []
        # 明確に凍結とみなす STUCK (overdue 下限以上) のみ対象
        stuck = {
            r["file"]: r for r in items
            if r.get("category") == "STUCK" and (r.get("overdue_ratio") or 0) >= min_overdue
        }
        current = set(stuck.keys())

        # 前回の state を読む
        state_path = self._alert_state_path()
        prev = set()
        first_run = True
        try:
            if state_path.exists():
                prev = set(json.loads(state_path.read_text(encoding="utf-8")).get("stuck", []))
                first_run = False
        except Exception:
            prev = set()

        # state を更新 (毎回保存)
        try:
            state_path.write_text(
                json.dumps({"stuck": sorted(current),
                            "updated": result.get("generated_at")}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"[StalenessMonitor] state save failed: {e}")

        if first_run:
            # 初回はベースライン記録のみ (既存の凍結で一斉通知しない)
            logger.info(f"[StalenessMonitor] alert baseline established ({len(current)} stuck)")
            return

        newly = sorted(current - prev)   # 新たに凍結
        resolved = sorted(prev - current)  # 解消
        if not newly and not resolved:
            return  # 変化なし → 通知しない

        sections = []
        if newly:
            lines = []
            for f in newly[:25]:
                r = stuck[f]
                lines.append(f"• `{f}` — latest {r.get('latest')} ({r.get('days_since_latest')}d)")
            if len(newly) > 25:
                lines.append(f"…他 {len(newly) - 25} 件")
            sections.append("🆕 **新たに凍結 (要調査)**\n" + "\n".join(lines))
        if resolved:
            sections.append("✅ **解消**\n" + "\n".join(f"• `{f}`" for f in resolved[:25]))

        description = "\n\n".join(sections) + (
            "\n\n詳細: `GET /api/admin/staleness?category=STUCK` (master)"
        )
        if len(description) > 4000:
            description = description[:3990] + "\n…(truncated)"

        color = 0xE67E22 if newly else 0x2ECC71  # 新規凍結=オレンジ / 解消のみ=緑
        title = f"⚠️ キャッシュ鮮度: 新規凍結 {len(newly)} / 解消 {len(resolved)}"
        payload = {
            "username": "Staleness Monitor",
            "embeds": [{
                "title": title,
                "description": description,
                "color": color,
                "footer": {"text": f"total {result.get('total')} caches | "
                                   f"STUCK now {len(current)} (overdue>={min_overdue})"},
            }],
        }
        resp = requests.post(webhook, json=payload, timeout=15)
        if resp.status_code not in (200, 204):
            logger.warning(
                f"[StalenessMonitor] Discord webhook returned {resp.status_code}: "
                f"{resp.text[:200]}"
            )
        else:
            logger.info(
                f"[StalenessMonitor] Discord notified (new={len(newly)}, resolved={len(resolved)})"
            )

    async def _scheduled_scan(self):
        try:
            logger.info("[StalenessMonitor] Daily cache staleness scan starting...")
            # 同期 I/O はスレッドへ (イベントループをブロックしない)
            self._last_result = await asyncio.to_thread(self._run_scan)
        except Exception as e:
            logger.error(f"[StalenessMonitor] Scan error: {e}")

    def start(self):
        try:
            self.scheduler.add_job(
                self._scheduled_scan,
                CronTrigger(hour=10, minute=30, timezone=JST),
                id="staleness_monitor",
                name="Cache Staleness Monitor",
                replace_existing=True,
                # セーフティネット自身が 10:30 を逃すと当日のスキャンが消える。
                # ループ詰まり・再起動跨ぎでも数時間以内なら実行する
                misfire_grace_time=6 * 3600,
            )
            # 起動時スキャン: 再起動すれば必ず一度は鮮度スキャンが走るようにする
            # (cron のみだと、毎日 10:30 前に再起動する運用では永久にスキャンされない)
            from apscheduler.triggers.date import DateTrigger
            from datetime import timedelta
            self.scheduler.add_job(
                self._scheduled_scan,
                DateTrigger(run_date=datetime.now(JST) + timedelta(minutes=3)),
                id="staleness_monitor_startup",
                name="Cache Staleness Monitor (startup)",
                replace_existing=True,
                misfire_grace_time=6 * 3600,
            )
            self.scheduler.start()
            logger.info("[StalenessMonitor] Scheduler started - Daily 10:30 JST + startup scan")
        except Exception as e:
            logger.error(f"[StalenessMonitor] Error starting scheduler: {e}")

    def shutdown(self):
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("[StalenessMonitor] Scheduler stopped")
        except Exception as e:
            logger.error(f"[StalenessMonitor] Error stopping scheduler: {e}")

    def get_status(self) -> Dict[str, Any]:
        jobs = []
        if self.scheduler.running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                })
        return {
            "running": self.scheduler.running,
            "jobs": jobs,
            "last_flagged": self._last_result.get("flagged"),
            "last_counts": self._last_result.get("counts"),
        }


# シングルトンインスタンス
staleness_monitor_scheduler = StalenessMonitorScheduler()
