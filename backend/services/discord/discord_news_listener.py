"""
Discord Gateway リスナー - FinancialJuice ニュースフィード

FinancialJuiceがDiscordチャンネルに投稿するニュースをリアルタイム受信し、
headlinesテーブルに保存する。翻訳はtranslation_workerに委任。
"""

import os
import asyncio
import traceback
from datetime import timezone

import discord

try:
    from backend.services.headlines.headlines_service import ingest_headline
except ImportError:
    from services.headlines.headlines_service import ingest_headline


class DiscordNewsListener:
    def __init__(self):
        self._channel_id = None
        self._task = None
        self._is_running = False
        self._token = None
        self.client = None

    def _create_client(self):
        """discord.Client を新規作成してイベントを登録"""
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)

        listener = self

        @self.client.event
        async def on_ready():
            print(f"[Discord] Logged in as {self.client.user}")
            listener._is_running = True
            await listener._backfill()

        @self.client.event
        async def on_message(message: discord.Message):
            if message.channel.id != listener.channel_id:
                return
            await listener._process_message(message)

        @self.client.event
        async def on_disconnect():
            print("[Discord] Disconnected from Gateway")
            listener._is_running = False

        @self.client.event
        async def on_resumed():
            print("[Discord] Resumed Gateway session")
            listener._is_running = True

    @property
    def channel_id(self) -> int:
        if self._channel_id is None:
            raw = os.getenv("DISCORD_FJ_CHANNEL_ID", "")
            if not raw:
                raise ValueError("DISCORD_FJ_CHANNEL_ID is not set in .env")
            self._channel_id = int(raw)
        return self._channel_id

    async def _backfill(self):
        """起動時に直近50件を取得し、未保存分をDBに挿入"""
        try:
            channel = self.client.get_channel(self.channel_id)
            if channel is None:
                channel = await self.client.fetch_channel(self.channel_id)

            count = 0
            async for message in channel.history(limit=50):
                saved = await self._process_message(message, quiet=True)
                if saved:
                    count += 1

            if count > 0:
                print(f"[Discord] Backfilled {count} messages")
            else:
                print("[Discord] Backfill: no new messages")
        except Exception as e:
            print(f"[Discord] Backfill error: {e}")

    async def _process_message(self, message: discord.Message, quiet: bool = False) -> bool:
        """メッセージを処理してheadlinesに保存。保存したらTrue。"""
        try:
            content = message.content or ""
            embed_title = ""
            embed_description = ""

            if message.embeds:
                embed = message.embeds[0]
                embed_title = embed.title or ""
                embed_description = embed.description or ""

            if not content and not embed_title and not embed_description:
                return False

            published_at = message.created_at.replace(tzinfo=timezone.utc) if message.created_at.tzinfo is None else message.created_at

            result = await asyncio.to_thread(
                ingest_headline,
                source_type="discord",
                headline_raw=content,
                published_at=published_at,
                source_message_id=message.id,
                source_channel_id=message.channel.id,
                embed_title=embed_title,
                embed_description=embed_description,
            )

            if result is not None:
                if not quiet:
                    preview = (content or embed_title)[:80]
                    print(f"[Discord] Saved: {preview}")
                return True
            return False

        except Exception as e:
            if not quiet:
                print(f"[Discord] Error processing message {message.id}: {e}")
            return False

    async def _run_with_reconnect(self):
        """自動再接続付きでBotを実行"""
        while True:
            try:
                self._create_client()
                print("[Discord] Connecting to Gateway...")
                await self.client.start(self._token)
            except Exception as e:
                self._is_running = False
                print(f"[Discord] Connection error: {e}")
                traceback.print_exc()
            finally:
                self._is_running = False
                if self.client and not self.client.is_closed():
                    try:
                        await self.client.close()
                    except Exception:
                        pass

            print("[Discord] Reconnecting in 30 seconds...")
            await asyncio.sleep(30)

    def start(self):
        """FastAPI startup から呼ばれる"""
        self._token = os.getenv("DISCORD_BOT_TOKEN", "")
        if not self._token:
            print("[Discord] DISCORD_BOT_TOKEN is not set, skipping")
            return
        if not os.getenv("DISCORD_FJ_CHANNEL_ID", ""):
            print("[Discord] DISCORD_FJ_CHANNEL_ID is not set, skipping")
            return

        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run_with_reconnect())
            print("[Discord] News listener starting...")
        except RuntimeError:
            print("[Discord] No running event loop, cannot start")

    def shutdown(self):
        """FastAPI shutdown から呼ばれる"""
        if self._task and not self._task.done():
            self._task.cancel()
        if self.client and not self.client.is_closed():
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.client.close())
            except RuntimeError:
                pass
        self._is_running = False
        print("[Discord] News listener stopped")

    def get_status(self) -> dict:
        """リスナーの状態を返す"""
        return {
            "is_running": self._is_running,
            "is_connected": self.client.is_ready() if self.client else False,
            "user": str(self.client.user) if self.client and self.client.user else None,
            "channel_id": self._channel_id,
            "task_alive": self._task is not None and not self._task.done() if self._task else False,
        }


discord_news_listener = DiscordNewsListener()
