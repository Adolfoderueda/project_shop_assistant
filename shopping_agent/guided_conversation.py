"""Opt-in guided dispatch; application choices precede model candidates."""

from collections.abc import Callable
from datetime import UTC, datetime

from conversation import Conversation
from dialogue import canonical_name, parse_answer
from dialogue_requests import known_greeting
from domain import IncomingCallback, IncomingEvent, Reply
from interpreter import parse_command, purchase_authorized
from shopping_agent.contracts import ToolCall
from shopping_agent.guided_contracts import ReadCandidate
from shopping_agent.guided_controller import resolve_text_choice
from shopping_agent.guided_ollama import GuidedOllamaAgent
from shopping_agent.guided_storage import RESET_REQUIRED
from shopping_agent.tools import AgentTools
from storage import Repository


class GuidedConversation:
    def __init__(self, repo: Repository, agent: GuidedOllamaAgent, legacy: Conversation,
                 *, clock: Callable[[], datetime] | None = None):
        self.repo, self.agent, self.legacy = repo, agent, legacy
        self.clock = clock or (lambda: datetime.now(UTC))

    async def handle(self, event: IncomingEvent, mode: str) -> Reply:
        if mode not in {'dry_run', 'live'}:
            raise ValueError('Invalid mode')
        stored, reply = self.repo.event_result(event.update_id)
        if stored != event:
            raise ValueError('Event does not match durable inbox')
        if reply is not None:
            return reply
        now = self.clock()
        if isinstance(event, IncomingCallback):
            return self.repo.apply_guided_callback(event.update_id, now=now)
        prepared = self.repo.prepared_presentation(event.update_id)
        if prepared is not None:
            return await self.legacy._present(prepared)
        if canonical_name(event.text) == 'cancelar':
            return self.repo.apply_guided(event.update_id, None,
                                          expected_question_version=None, now=now)
        # Queries and genuine slash commands retain their deterministic route;
        # free text cannot silently resurrect any expired guided or legacy recipient.
        if (not event.text.strip().startswith('/') and not purchase_authorized(event.text)
                and self.repo.guided_reset_required(event.update_id, now=now)):
            return self.repo.complete_agent_reply(event.update_id, Reply(text=RESET_REQUIRED))
        self.repo.set_conversation_route(event.user_id, event.chat_id, 'agent', now=now)
        if event.text.strip().startswith('/') or purchase_authorized(event.text):
            command = parse_command(event.text, self.repo.list_lines())
            if command is None or command.action not in {'list', 'fiche', 'status'}:
                self.repo.revoke_guided(event.user_id, now=now)
            return await self.legacy.handle(event, mode)
        origin = self.repo.command_origin(event.user_id, event.chat_id)
        if origin is not None:
            command_state = self.repo.dialogue_state(event.user_id, event.chat_id, now=now)
            if parse_answer(event.text, command_state, now=now) is not None:
                self.repo.revoke_guided(event.user_id, now=now)
                return self.repo.apply_dialogue(event.update_id, None, mode, now=now)
        state = self.repo.guided_state(event.update_id, now=now)
        version = state.question.version if state.question else None
        choice = resolve_text_choice(event, state.question) if state.question else None
        if choice is not None:
            return self.repo.apply_guided(event.update_id, choice,
                                          expected_question_version=version, now=now)
        if known_greeting(event.text):
            return await self.legacy.handle(event, mode)
        if canonical_name(event.text) == 'cancelar':
            return self.repo.apply_guided(event.update_id, None,
                                          expected_question_version=version, now=now)
        try:
            history = self.repo.guided_history(event.user_id, event.chat_id)
        except ValueError:
            # Unvalidated history must never become prompt context or permission.
            return self.repo.complete_agent_reply(event.update_id,
                Reply(text='No puedo validar el contexto anterior. Aclara la petición; no se ha cambiado el borrador.'))
        result = await self.agent.interpret(event, state, history)
        now = self.clock()  # Inference can outlive the durable question/proposal.
        answer = result.answer  # Inert failures remain the actual clarify candidate.
        if isinstance(answer, ReadCandidate):
            tools = AgentTools(self.repo, event, now=now)
            call = ToolCall(name='consultar_lista' if answer.kind == 'list' else 'consultar_ficha',
                            arguments={} if answer.kind == 'list' else {'query': answer.query})
            call, = tools.validate_calls((call,))
            return self.repo.complete_agent_reply(event.update_id, tools.execute(call).reply)
        return self.repo.apply_guided(event.update_id, answer,
                                      expected_question_version=version, now=now)
