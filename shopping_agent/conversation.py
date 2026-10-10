"""Opt-in routing: durable recovery, explicit commands, then native tools."""

from collections.abc import Callable
from datetime import UTC, datetime

from conversation import Conversation
from dialogue import parse_answer
from dialogue_requests import known_greeting
from domain import IncomingMessage, Intent, Reply
from interpreter import purchase_authorized
from shopping_agent.ollama import OllamaShoppingAgent
from shopping_agent.tools import AgentTools
from storage import Repository


class AgentConversation:
    def __init__(self, repo: Repository, agent: OllamaShoppingAgent, legacy: Conversation,
                 *, clock: Callable[[], datetime] | None = None):
        self.repo = repo
        self.agent = agent
        self.legacy = legacy
        self.clock = clock or (lambda: datetime.now(UTC))

    async def handle(self, message: IncomingMessage, mode: str) -> Reply:
        if mode not in {'dry_run', 'live'}:
            raise ValueError('Invalid mode')
        stored, reply = self.repo.message_result(message.update_id)
        if stored != message:
            raise ValueError('Message does not match durable inbox')
        if reply is not None:
            return reply
        prepared = self.repo.prepared_presentation(message.update_id)
        if prepared is not None:
            return await self.legacy._present(prepared)
        now = self.clock()
        # This engine is the flag-off rollback path, never a v2 reducer.
        self.repo.revoke_guided(message.user_id, now=now)
        self.repo.set_conversation_route(message.user_id, message.chat_id, 'agent', now=now)
        if message.text.strip().startswith('/') or purchase_authorized(message.text):
            return await self.legacy.handle(message, mode)
        if known_greeting(message.text):
            return self.repo.apply_dialogue(message.update_id, Intent(action='greet'), mode, now=now)
        origin = self.repo.command_origin(message.user_id, message.chat_id)
        if origin is not None:
            state = self.repo.dialogue_state(message.user_id, message.chat_id, now=now)
            if parse_answer(message.text, state, now=now) is not None:
                # Bypass legacy's broad free-text aliases/interpreter completely.
                return self.repo.apply_dialogue(message.update_id, None, mode, now=now)
        reply = self.repo.apply_agent_control(message.update_id, now=now)
        if reply is not None:
            return reply
        tools = AgentTools(self.repo, message, now=now)
        result = await self.agent.run(message, tools)
        return self.repo.complete_agent_reply(message.update_id, result.reply)
