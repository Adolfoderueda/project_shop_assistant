"""Deterministic guided-state fixtures; no repository or token authority."""

from datetime import UTC, datetime
from uuid import UUID

from dialogue import DIALOGUE_TTL, LineRef
from domain import IncomingCallback, IncomingMessage, ListLine
from shopping_agent.contracts import (
    AgentSnapshot,
    Contribution,
    GuidedProposal,
    ItemPatch,
    ProposalItem,
    Reservation,
)
from shopping_agent.guided_contracts import GuidedState, QuantityCandidate

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


def topic_state_fixture():
    """An additional topic suspends a complete main draft's review."""
    from shopping_agent.contracts import ItemInput, ProposeAdds
    from shopping_agent.guided_contracts import TopicCandidate
    from shopping_agent.guided_controller import reduce_guided

    state = reduce_guided(state_fixture(quantities=(1, 1, 1)), message(2, 'revisar'), None, now=NOW).state
    return reduce_guided(state, message(3, 'leche'), TopicCandidate(source_update_id=3,
        adds=ProposeAdds(items=(ItemInput(description='leche'),))), now=NOW).state


def candidate(update, *pairs):
    return QuantityCandidate(source_update_id=update,
                             patches=tuple(ItemPatch(position=p, quantity=q) for p, q in pairs))


def with_items(items, *, lines=(), reservations=(), original_text='petición'):
    state = state_fixture()
    proposal = state.snapshot.proposal.model_copy(update={'items': items, 'original_text': original_text,
        'contributions': (Contribution(update_id=1, positions=tuple(i.position for i in items), kind='create'),)})
    return state.model_copy(update={'snapshot': state.snapshot.model_copy(update={
        'proposal': proposal, 'lines': lines, 'reservations': reservations})})


def increment_state(*, base=2, reserved=False, selected=True):
    line = ListLine(id='line', revision=1, description='leche', quantity=base)
    ref = LineRef(id=line.id, revision=line.revision)
    return with_items((ProposalItem(position=1, kind='increment', description='leche',
        candidates=(ref,), conflict_signatures=(ref,), target=ref if selected else None,
        base_quantity=base if selected else None, additional_quantity=3,
        quantity=base + 3 if selected and base is not None else None),), lines=(line,),
        reservations=(Reservation(line_id='line', order_id='order'),) if reserved else ())
