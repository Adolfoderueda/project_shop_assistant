import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from conversation import Conversation
from domain import IncomingCallback, Intent
from runtime import _CommandsOnly
from shopping_agent.guided_conversation import GuidedConversation
from shopping_agent.guided_ollama import GuidedOllamaAgent
from telegram_io import TelegramIO
from tests.fakes import FakeBot
from tests.guided_helpers import (
    PurchaseBlockedConversation,
    PurchaseBlockedRepository,
    guided_http_response,
)


class Session:
    def __init__(self, tmp_path):
        self.repo = PurchaseBlockedRepository(tmp_path / 'guided.db')
        self.repo.migrate()
        self.now = datetime.now(UTC)
        self.bot = FakeBot()
        self.io = TelegramIO(self.bot, self.repo, 7)
        self.responses = []
        self.calls = []

        def respond(request):
            self.calls.append(request)
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return guided_http_response(response) if isinstance(response, str) else response

        self.agent = GuidedOllamaAgent(transport=httpx.MockTransport(respond))
        self.legacy = Conversation(self.repo, _CommandsOnly(), clock=lambda: self.now)
        self.conversation = GuidedConversation(self.repo, self.agent, self.legacy, clock=lambda: self.now)
        self.guard = PurchaseBlockedConversation(self.repo, self.conversation)
        self.number = 0

    def send(self, text, response=None):
        self.number += 1
        if response is not None:
            self.responses.append(response)
        self.bot.receive(self.number, text)

        async def turn():
            await self.io.poll_once()
            event, _ = self.repo.event_result(self.number)
            reply = await self.guard.handle(event, 'dry_run')
            await self.io.send_pending()
            assert self.repo.pending_orders() == self.repo.resumable_orders() == []
            return reply

        return asyncio.run(turn())

    def propose(self, names, quantity=None):
        response = httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {
            'role': 'assistant', 'tool_calls': [{'function': {'name': 'proponer_altas',
                'arguments': {'items': [{'description': name, 'quantity': quantity} for name in names]}}}]}})
        return self.send(', '.join(names), response)

    def new_topic(self, text):
        return self.send(text, 'milk')

    def state(self):
        return self.repo.guided_state(self.number, now=self.now)

    def pending_names(self):
        return [i.description for i in self.state().snapshot.proposal.items]

    def saved(self):
        return self.repo.list_lines()


@pytest.fixture
def guided_session(tmp_path):
    return Session(tmp_path)


def test_topic_no_preserves_main_and_scope_yes_does_not_save(guided_session):
    s = guided_session
    s.propose(['huevos', 'carne', 'atun'])
    s.new_topic('leche')
    s.send('no')
    assert s.pending_names() == ['huevos', 'carne', 'atun']
    assert s.saved() == []
    s.send('uno para todos', 'candidate_all')
    assert s.state().question.kind == 'scope'
    s.send('sí', 'clarify')
    assert s.saved() == []
    assert [i.quantity for i in s.state().snapshot.proposal.items] == [None, None, None]
    s.send('Todos')
    assert [i.quantity for i in s.state().snapshot.proposal.items] == [1, 1, 1]
    assert len(s.calls) == 4


def test_complete_review_mixed_yes_edits_then_separate_yes_saves_once(guided_session):
    s = guided_session
    s.propose(['huevos', 'carne', 'atun'], quantity=1)
    old = s.state().review
    s.send('sí pero huevos dos', 'edit_complete')
    assert s.saved() == []
    assert s.state().review is None
    s.send('huevos')  # Explicit scope authorizes the candidate, not model prose.
    assert s.state().review.question_id != old.question_id
    assert s.state().snapshot.proposal.items[0].quantity == 2
    reply = s.send('sí')
    rows = s.saved()
    assert len(rows) == 3
    event, _ = s.repo.event_result(s.number)
    assert asyncio.run(s.conversation.handle(event, 'dry_run')) == reply
    assert s.saved() == rows


@pytest.mark.parametrize('query,response', [('qué lista tengo', 'list'), ('ficha leche', 'fiche'), ('/lista', None)])
def test_queries_preserve_question_review_and_expiry(guided_session, query, response):
    s = guided_session
    s.propose(['huevos', 'carne', 'atun'], quantity=1)
    before = s.state()
    reply = s.send(query, response)
    after = s.state()
    assert after.question == before.question
    assert after.review == before.review
    assert after.snapshot.proposal == before.snapshot.proposal
    assert reply.keyboard is None
    assert ('lista' in reply.text.casefold() or 'históricas' in reply.text)
    assert s.saved() == []


def test_model_failure_and_invalid_history_are_inert(guided_session, monkeypatch):
    s = guided_session
    s.propose(['huevos', 'carne', 'atun'], quantity=1)
    before = s.state().snapshot.proposal
    s.send('cambia algo', httpx.ConnectError('offline'))
    assert s.saved() == []
    assert s.state().snapshot.proposal.items == before.items
    before = s.state()
    calls = len(s.calls)
    monkeypatch.setattr(s.repo, 'guided_history', lambda *a: (_ for _ in ()).throw(ValueError('corrupt')))
    reply = s.send('otra petición')
    assert len(s.calls) == calls
    assert s.state().question == before.question
    assert s.state().snapshot.proposal == before.snapshot.proposal
    assert reply.keyboard is None
    assert s.saved() == []


def test_expired_lista_and_new_request_do_not_reuse_old_permission(guided_session):
    s = guided_session
    s.propose(['huevos', 'carne', 'atun'])
    old = s.state().question
    s.now += timedelta(minutes=16)
    s.send('/lista')
    assert s.state().question == old
    s.new_topic('leche')
    assert s.pending_names() == ['leche']
    assert s.state().question.id != old.id


def test_callback_dispatch_uses_original_event_without_model(guided_session):
    s = guided_session
    reply = s.propose(['huevos', 'carne', 'atun'])
    token = reply.keyboard.rows[0][0].token
    s.number += 1
    event = IncomingCallback(update_id=s.number, user_id=7, chat_id=7,
        bot_id=99, message_id=1, callback_query_id='known', data=token)
    s.repo.ingest_events([event], s.number + 1)
    # FakeBot delivered the original keyboard as actual message 1.
    asyncio.run(s.conversation.handle(event, 'dry_run'))
    assert s.repo.event_result(s.number)[0] == event
    assert len(s.calls) == 1
    assert s.saved() == []
    assert [i.quantity for i in s.state().snapshot.proposal.items] == [1, 1, 1]


def test_identity_and_mode_are_checked_before_dispatch(guided_session):
    s = guided_session
    s.propose(['huevos'])
    event, _ = s.repo.event_result(1)
    with pytest.raises(ValueError):
        asyncio.run(s.conversation.handle(event.model_copy(update={'text': 'sí'}), 'dry_run'))
    with pytest.raises(ValueError):
        asyncio.run(s.conversation.handle(event, 'unsafe'))


@pytest.mark.parametrize('text', ['/comprar', 'comprar lo pendiente', '/continuar pedido'])
def test_purchase_guard_and_write_boundary_are_both_blocked(guided_session, text):
    s = guided_session
    reply = s.send(text)
    assert 'bloqueadas' in reply.text
    assert s.repo.pending_orders() == s.repo.resumable_orders() == []
    with pytest.raises(PermissionError), s.repo._connection(write=True) as db:
        s.repo._apply(db, s.number, Intent(action='buy'), 'dry_run')
    with pytest.raises(PermissionError), s.repo._connection(write=True) as db:
        s.repo._apply(db, s.number, Intent(action='resume', order_id='pedido'), 'dry_run')


def test_genuine_offered_text_never_needs_model_even_when_unavailable(guided_session):
    s = guided_session
    s.propose(['huevos', 'carne', 'atun'], quantity=1)
    s.responses.append(httpx.ConnectError('unavailable'))
    s.send('sí')
    assert len(s.calls) == 1
    assert len(s.saved()) == 3


def test_new_topic_yes_appends_without_saving_or_losing_originals(guided_session):
    s = guided_session
    s.propose(['huevos', 'carne', 'atun'])
    original = s.state().snapshot.proposal.original_text
    s.new_topic('leche')
    s.send('sí')
    assert s.pending_names() == ['huevos', 'carne', 'atun', 'leche']
    assert s.saved() == []
    assert s.state().snapshot.proposal.original_text == original
    assert [i.quantity for i in s.state().snapshot.proposal.items] == [None] * 4


def test_internal_duplicates_require_application_decision_never_auto_sum(guided_session):
    s = guided_session
    s.propose(['leche', 'leche'], quantity=1)
    assert s.state().question.kind == 'duplicate'
    assert [i.quantity for i in s.state().snapshot.proposal.items] == [1, 1]
    assert s.saved() == []
    while s.state().question.kind == 'duplicate':
        choice = next(c for c in s.state().question.choices if c.kind == 'separate')
        s.send(choice.label)
    s.send('sí')
    assert len(s.saved()) == 2
    assert [line.quantity for line in s.saved()] == [1, 1]


def test_slash_mutation_revokes_only_pending_permission_not_saved_rows(guided_session):
    s = guided_session
    s.propose(['huevos'], quantity=1)
    s.send('sí')
    saved = s.saved()
    s.propose(['carne'])
    s.new_topic('leche')
    s.send('/anadir arroz 2')
    assert s.state().snapshot.proposal is None
    assert s.state().topic is None
    assert all(line in s.saved() for line in saved)


def test_natural_list_distinguishes_actual_saved_rows_and_pending_draft(guided_session):
    s = guided_session
    s.propose(['huevos'], quantity=1)
    s.send('sí')
    saved = s.saved()
    s.propose(['carne'])
    before = s.state()
    reply = s.send('qué lista tengo', 'list')
    assert 'huevos' in reply.text and 'carne' not in reply.text
    assert 'propuestas no están guardadas' in reply.text
    assert s.saved() == saved
    assert s.state().question == before.question


def test_slash_question_keeps_legacy_command_origin_answers_without_model(guided_session):
    s = guided_session
    s.send('/anadir arroz')
    assert s.saved() == []
    s.send('2')
    assert len(s.calls) == 0
    assert len(s.saved()) == 1
    assert s.saved()[0].description == 'arroz'
    assert s.saved()[0].quantity == 2


@pytest.mark.parametrize('text', ['/comprar', 'comprar lo pendiente', '/continuar pedido'])
def test_unwrapped_conversation_preserves_legacy_purchase_write_guard(guided_session, text):
    s = guided_session
    s.propose(['huevos'], quantity=1)
    s.send('sí')
    saved = s.saved()
    s.propose(['carne'])
    s.number += 1
    from tests.guided_helpers import message
    event = message(s.number, text)
    s.repo.ingest_events([event], s.number + 1)
    with pytest.raises(PermissionError, match='Purchases blocked'):
        asyncio.run(s.conversation.handle(event, 'dry_run'))
    assert s.repo.guided_state(s.number, now=s.now).snapshot.proposal is None
    assert s.saved() == saved
    assert s.repo.pending_orders() == s.repo.resumable_orders() == []


def test_shared_quantity_only_updates_the_explicit_offered_group(guided_session):
    s = guided_session
    s.propose(['huevos', 'carne', 'atun'])
    expires = s.state().snapshot.proposal.expires_at
    s.send('Misma cantidad')
    assert s.state().question.kind == 'quantity_shared'
    s.send('dos', 'focused_two')
    assert [i.quantity for i in s.state().snapshot.proposal.items] == [2, 2, 2]
    assert s.state().snapshot.proposal.expires_at == expires
    assert s.saved() == []
    assert s.state().question.kind == 'review'
    s.send('sí')
    assert len(s.saved()) == 3


def test_offered_product_named_hola_is_selection_not_greeting(guided_session):
    s = guided_session
    s.propose(['hola', 'carne', 'atun'])
    s.send('uno', 'candidate_all')
    assert s.state().question.kind == 'scope'
    s.send('hola')
    assert [i.quantity for i in s.state().snapshot.proposal.items] == [1, None, None]
    assert s.saved() == []
    assert len(s.calls) == 2
