"""Durable Telegram transport; inbox dispatch belongs to the application runner."""

import asyncio
import logging
from datetime import timedelta

from telegram import Bot, LinkPreviewOptions, MessageEntity
from telegram.error import BadRequest, NetworkError, RetryAfter, TelegramError

from domain import IncomingMessage
from storage import Repository

logger = logging.getLogger(__name__)


class TelegramIO:
    """Use one instance/worker per bot; lifecycle and dispatch belong to task 7.

    Notifications are at-least-once: a lost send response or crash before the
    sent marker may duplicate a notice (or an already sent chunk), never an order.
    """

    def __init__(self, bot: Bot, repo: Repository, allowed_user_id: int):
        if type(allowed_user_id) is not int or allowed_user_id <= 0:
            raise ValueError("Authorized user ID must be a positive integer")
        self.bot = bot
        self.repo = repo
        self.allowed_user_id = allowed_user_id

    async def poll_once(self) -> None:
        updates = await self.bot.get_updates(
            offset=self.repo.telegram_offset(),
            allowed_updates=["message"],
            limit=100,
            timeout=30,
            read_timeout=5,  # PTB adds the long-poll timeout (35 seconds total).
            write_timeout=10,
            connect_timeout=10,
            pool_timeout=5,
        )
        if not updates:
            return
        messages = []
        for update in updates:
            message = update.message
            if (
                message is not None
                and message.from_user is not None
                and message.from_user.id == self.allowed_user_id
                and not message.from_user.is_bot
                and message.chat.type == "private"
                and message.chat.id == self.allowed_user_id
                and message.text is not None
                # IncomingMessage carries no provenance: reject relayed/quoted
                # content before reducing it to potentially executable plain text.
                and message.forward_origin is None
                and not message.is_automatic_forward
                and message.quote is None
                and message.via_bot is None
                and message.sender_business_bot is None
                and message.sender_chat is None
                and not any(entity.type in (
                    MessageEntity.BLOCKQUOTE, MessageEntity.EXPANDABLE_BLOCKQUOTE,
                ) for entity in message.entities)
            ):
                messages.append(IncomingMessage(
                    update_id=update.update_id,
                    user_id=message.from_user.id,
                    chat_id=message.chat.id,
                    text=message.text,
                ))
        # Include ignored updates in the offset, but never persist their content.
        # Failure propagates: the next call reloads only the committed offset.
        self.repo.ingest_batch(messages, max(u.update_id for u in updates) + 1)

    async def send_pending(self) -> None:
        for notice_id, chat_id, text in self.repo.pending_notices():
            if chat_id != self.allowed_user_id:
                logger.warning("Blocked notice %s", notice_id)
                continue
            # 2000 Unicode code points fit even if all use two UTF-16 code units.
            # An empty notice is rejected by Telegram and remains pending.
            chunks = [text[i:i + 2000] for i in range(0, len(text), 2000)] or [text]
            for chunk in chunks:
                if not await self._send_chunk(notice_id, chat_id, chunk):
                    break
            else:
                self.repo.mark_notice_sent(notice_id)
                logger.info("Sent notice %s", notice_id)

    async def _send_chunk(self, notice_id: str, chat_id: int, text: str) -> bool:
        for attempt in range(3):
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=None,
                    entities=None,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                    read_timeout=20,
                    write_timeout=20,
                    connect_timeout=10,
                    pool_timeout=5,
                )
                return True
            except RetryAfter as error:
                delay = error.retry_after
                seconds = delay.total_seconds() if isinstance(delay, timedelta) else delay
                logger.warning("Rate limited notice %s", notice_id)
                # Wait even on the last attempt so the next notice/call respects it.
                await asyncio.sleep(seconds)
            except BadRequest:
                # BadRequest subclasses NetworkError, but retrying it cannot help.
                logger.warning("Rejected notice %s", notice_id)
                return False
            except NetworkError:
                logger.warning("Delivery uncertain for notice %s", notice_id)
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
            except TelegramError:
                logger.warning("Unable to send notice %s", notice_id)
                return False
        return False
