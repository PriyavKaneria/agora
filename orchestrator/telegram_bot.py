from __future__ import annotations

import asyncio
from typing import Iterable

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from orchestrator.config import TelegramConfig
from orchestrator.pipeline import OrchestratorService
from orchestrator.storage import Storage


def _chunk_message(text: str, chunk_size: int = 3800) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


class TelegramControlBot:
    def __init__(self, config: TelegramConfig, service: OrchestratorService, storage: Storage):
        if not config.bot_token:
            raise ValueError("telegram.bot_token is required")
        self.config = config
        self.service = service
        self.storage = storage
        self.allowed_chat_ids = set(config.allowed_chat_ids)

    def run(self) -> None:
        app = Application.builder().token(self.config.bot_token).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help))
        app.add_handler(CommandHandler("scan", self.scan))
        app.add_handler(CommandHandler("list", self.list_pending))
        app.add_handler(CommandHandler("show", self.show))
        app.add_handler(CommandHandler("approve", self.approve))
        app.add_handler(CommandHandler("reject", self.reject))
        app.add_handler(CommandHandler("chatid", self.chat_id))

        interval_sec = max(self.config.scan_interval_minutes, 1) * 60
        app.job_queue.run_repeating(self.periodic_scan, interval=interval_sec, first=10)
        app.run_polling(close_loop=False)

    async def _authorized(self, update: Update) -> bool:
        if update.effective_chat is None:
            return False
        chat_id = update.effective_chat.id
        if not self.allowed_chat_ids:
            return True
        return chat_id in self.allowed_chat_ids

    async def _deny_if_unauthorized(self, update: Update) -> bool:
        if await self._authorized(update):
            return False
        if update.effective_message:
            await update.effective_message.reply_text(
                "This chat is not allowed. Add the chat id to `telegram.allowed_chat_ids`."
            )
        return True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_unauthorized(update):
            return
        await update.effective_message.reply_text(
            "Agora control commands:\n"
            "/scan - run scan now\n"
            "/list - show pending IDs\n"
            "/show <id> - show all drafts for a candidate\n"
            "/approve <id> <1|2|3> - send selected draft\n"
            "/reject <id> - mark candidate rejected\n"
            "/chatid - show this chat id"
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.start(update, context)

    async def chat_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message and update.effective_chat:
            await update.effective_message.reply_text(f"chat_id={update.effective_chat.id}")

    async def scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_unauthorized(update):
            return
        if update.effective_message:
            await update.effective_message.reply_text("Running scan...")
        created = await asyncio.to_thread(self.service.scan_once)
        if not created:
            await update.effective_message.reply_text("No new high-relevance posts found.")
            return
        await self._send_candidates(update.effective_chat.id, created, context.bot)

    async def periodic_scan(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        created = await asyncio.to_thread(self.service.scan_once)
        if not created:
            return
        target_chat_ids: Iterable[int]
        if self.allowed_chat_ids:
            target_chat_ids = self.allowed_chat_ids
        else:
            return
        for chat_id in target_chat_ids:
            await self._send_candidates(chat_id, created, context.bot)

    async def list_pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_unauthorized(update):
            return
        pending = await asyncio.to_thread(self.storage.list_pending, 15)
        if not pending:
            await update.effective_message.reply_text("No pending candidates.")
            return
        lines = ["Pending candidates:"]
        lines.extend(f"- {p.candidate.candidate_id} ({p.candidate.relevance_score:.3f})" for p in pending)
        await update.effective_message.reply_text("\n".join(lines))

    async def show(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_unauthorized(update):
            return
        if not context.args:
            await update.effective_message.reply_text("Usage: /show <candidate_id>")
            return
        candidate_id = context.args[0].strip()
        try:
            full = await asyncio.to_thread(self.service.format_full_drafts, candidate_id)
        except Exception as e:
            await update.effective_message.reply_text(str(e))
            return
        for chunk in _chunk_message(full):
            await update.effective_message.reply_text(chunk)

    async def approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_unauthorized(update):
            return
        if len(context.args) < 2:
            await update.effective_message.reply_text("Usage: /approve <candidate_id> <1|2|3>")
            return
        candidate_id = context.args[0].strip()
        try:
            draft_index = int(context.args[1])
            result = await asyncio.to_thread(self.service.approve_pending, candidate_id, draft_index)
        except Exception as e:
            await update.effective_message.reply_text(f"Approve failed: {e}")
            return
        await update.effective_message.reply_text(f"Approved and sent. Result: {result}")

    async def reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._deny_if_unauthorized(update):
            return
        if not context.args:
            await update.effective_message.reply_text("Usage: /reject <candidate_id>")
            return
        candidate_id = context.args[0].strip()
        reason = " ".join(context.args[1:]).strip()
        try:
            await asyncio.to_thread(self.service.reject_pending, candidate_id, reason)
        except Exception as e:
            await update.effective_message.reply_text(f"Reject failed: {e}")
            return
        await update.effective_message.reply_text(f"Rejected: {candidate_id}")

    async def _send_candidates(self, chat_id: int, created, bot: Bot) -> None:
        for pending in created:
            text = self.service.format_candidate_for_message(pending)
            for chunk in _chunk_message(text):
                await bot.send_message(chat_id=chat_id, text=chunk, disable_web_page_preview=True)
