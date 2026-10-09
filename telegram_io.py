"""Durable Telegram transport; inbox dispatch belongs to the application runner."""

import asyncio
import logging
import re
from datetime import timedelta
from hashlib import sha256

from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
    MessageEntity,
)
from telegram.error import BadRequest, NetworkError, RetryAfter, TelegramError

from domain import IncomingCallback, IncomingMessage
from shopping_agent.guided_replies import review_fits
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
        # Recovery must not depend on a new update or business dispatch succeeding.
        await self.ack_callbacks()
        updates = await self.bot.get_updates(
            offset=self.repo.telegram_offset(),
            allowed_updates=["message", "callback_query"],
            limit=100,
            timeout=30,
            read_timeout=5,  # PTB adds the long-poll timeout (35 seconds total).
            write_timeout=10,
            connect_timeout=10,
            pool_timeout=5,
        )
        if not updates:
            return
        events = []
        me = await self.bot.get_me() if any(u.callback_query is not None for u in updates) else None
        for update in updates:
            query = update.callback_query
            if query is not None:
                message = query.message
                if (
                    query.from_user.id == self.allowed_user_id
                    and not query.from_user.is_bot
                    and query.inline_message_id is None
                    and query.game_short_name is None
                    and isinstance(message, Message)
                    and message.chat.type == "private"
                    and message.chat.id == self.allowed_user_id
                    and message.from_user is not None
                    and message.from_user.is_bot
                    and me.is_bot
                    and message.from_user.id == me.id
                    and type(query.data) is str
                    and re.fullmatch(r"q:[A-Za-z0-9_-]{22}", query.data)
                    and type(message.message_id) is int and message.message_id > 0
                    and type(query.id) is str and query.id
                ):
                    events.append(IncomingCallback(
                        update_id=update.update_id, user_id=query.from_user.id,
                        chat_id=message.chat.id, callback_query_id=query.id,
                        message_id=message.message_id, bot_id=me.id, data=query.data,
                    ))
                continue
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
                events.append(IncomingMessage(
                    update_id=update.update_id,
                    user_id=message.from_user.id,
                    chat_id=message.chat.id,
                    text=message.text,
                ))
        # Include ignored updates in the offset, but never persist their content.
        # Failure propagates: the next call reloads only the committed offset.
        self.repo.ingest_events(events, max(u.update_id for u in updates) + 1)
        await self.ack_callbacks()

    async def ack_callbacks(self) -> None:
        queries = self.repo.pending_callback_acks()
        if queries:
            # The query-only public API must not authorize foreign retained work.
            self.repo.assert_authorized_owner(self.allowed_user_id)
        for query_id in queries:
            try:
                # No success text: this acknowledges reception, not an operation.
                await self.bot.answer_callback_query(callback_query_id=query_id)
            except BadRequest as error:
                reason = str(error).lower()
                if any(marker in reason for marker in (
                    "query is too old", "query id is invalid", "query_id_invalid",
                )):
                    self.repo.mark_callback_ack(query_id, expired=True)
                else:
                    logger.warning("Callback acknowledgement rejected")
            except TelegramError:
                # Network/rate-limit errors stay pending for the next call/restart.
                logger.warning("Callback acknowledgement pending")
            else:
                self.repo.mark_callback_ack(query_id)

    async def send_pending(self) -> None:
        for notice_id, chat_id, reply in self.repo.pending_replies():
            if chat_id != self.allowed_user_id:
                logger.warning("Blocked notice %s", notice_id)
                continue
            text = reply.text
            markup = None
            if reply.keyboard is not None:
                if not review_fits(reply):
                    # An invalid producer must never deliver a truncated authority.
                    logger.warning("Oversized guided notice %s; split request required", notice_id)
                    continue
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton(button.label, callback_data=button.token) for button in row]
                    for row in reply.keyboard.rows
                ])
            # 2000 Unicode code points fit even if all use two UTF-16 code units.
            # An empty notice is rejected by Telegram and remains pending.
            chunks = ([text] if markup is not None else
                      [text[i:i + 2000] for i in range(0, len(text), 2000)] or [text])
            digest = sha256(text.encode("utf-8")).hexdigest()
            for chunk in chunks:
                if not await self._send_chunk(notice_id, chat_id, chunk, digest, markup):
                    break
            else:
                self.repo.mark_notice_sent(notice_id)
                logger.info("Sent notice %s", notice_id)

    async def _send_chunk(self, notice_id: str, chat_id: int, text: str,
                          digest: str, markup: InlineKeyboardMarkup | None) -> bool:
        for attempt in range(3):
            try:
                sent = await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=None,
                    entities=None,
                    reply_markup=markup,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                    read_timeout=20,
                    write_timeout=20,
                    connect_timeout=10,
                    pool_timeout=5,
                )
                if not isinstance(sent, Message) or sent.chat.id != chat_id or sent.chat.type != "private":
                    raise ValueError("Invalid Telegram delivery response")
                self.repo.record_delivery(notice_id, chat_id, sent.message_id, digest)
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
