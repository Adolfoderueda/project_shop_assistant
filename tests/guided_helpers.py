"""Deterministic guided-state fixtures; no repository or token authority."""

from datetime import UTC, datetime
from uuid import UUID

from dialogue import DIALOGUE_TTL
from domain import IncomingCallback, IncomingMessage
from shopping_agent.contracts import AgentSnapshot, Contribution, GuidedProposal, ProposalItem
from shopping_agent.guided_contracts import GuidedState

NOW = datetime(2026, 10, 9, tzinfo=UTC)
VALID_TOKEN = 'q:' + 'A' * 22


def message(update_id, text, owner=7):
    return IncomingMessage(update_id=update_id, user_id=owner, chat_id=owner, text=text)


def callback(update_id, token, query_id='query', message_id=100, owner=7, bot_id=99):
    return IncomingCallback(update_id=update_id, user_id=owner, chat_id=owner,
                            callback_query_id=query_id, message_id=message_id,
                            bot_id=bot_id, data=token)


def state_fixture(*, quantities=(None, None, None), now=NOW, condition=None):
    items = tuple(ProposalItem(position=i, kind='add', description=name, quantity=quantity)
                  for i, (name, quantity) in enumerate(
                      zip(('huevos', 'carne', 'atun'), quantities, strict=True), 1))
    proposal = GuidedProposal(
        id=UUID('00000000-0000-0000-0000-000000000001'), revision=1,
        user_id=7, chat_id=7, source_update_id=1, original_text='huevos carne atun',
        items=items, condition=condition, updated_at=now, expires_at=now + DIALOGUE_TTL,
        contributions=(Contribution(update_id=1, positions=(1, 2, 3), kind='create'),),
    )
    return GuidedState(snapshot=AgentSnapshot(
        proposal=proposal, user_id=7, chat_id=7, source_update_id=1,
        original_text=proposal.original_text), question=None, topic=None, review=None)
