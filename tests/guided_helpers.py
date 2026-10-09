"""Pure fixtures and inbox-backed guided repository cases."""

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
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


@dataclass
class PersistedCase:
    repo: object
    now: datetime
    source_update_id: int = 1

    def question(self):
        return self.repo.guided_state(self.source_update_id, now=self.now).question

    def choice_token(self, kind):
        q = self.question()
        index = next(i for i, c in enumerate(q.choices) if c.kind == kind)
        with self.repo._connection() as db:
            return db.execute('SELECT token FROM guided_tokens WHERE question_id=? AND question_version=? '
                              'AND choice_index=?', (str(q.id), q.version, index)).fetchone()[0]

    def record_known_delivery(self, message_id=100):
        from shopping_agent.guided_replies import render_question

        q = self.question()
        with self.repo._connection() as db:
            notice = db.execute('SELECT notice_id FROM guided_questions WHERE id=? AND version=?',
                                (str(q.id), q.version)).fetchone()[0]
        self.repo.record_delivery(notice, 7, message_id, sha256(render_question(q).text.encode('utf-8')).hexdigest())

    def ingest_message(self, update_id, text):
        self.repo.ingest_events([message(update_id, text)], update_id + 1)

    def ingest_callback(self, update_id, token, message_id=100, query_id=None):
        self.repo.ingest_events([callback(update_id, token, query_id=query_id or f'query-{update_id}',
                                          message_id=message_id)], update_id + 1)


def persisted_case(tmp_path, *, quantities=(None, None, None), condition=None):
    from shopping_agent.contracts import ItemInput, ProposeAdds
    from shopping_agent.guided_contracts import TopicCandidate
    from storage import Repository

    repo = Repository(tmp_path / 'guided.db')
    repo.migrate()
    c = PersistedCase(repo=repo, now=datetime.now(UTC))
    c.ingest_message(1, 'huevos carne atun')
    answer = TopicCandidate(source_update_id=1, adds=ProposeAdds(condition=condition,
        items=tuple(ItemInput(description=name, quantity=q) for name, q in
                    zip(('huevos', 'carne', 'atun'), quantities, strict=True))))
    repo.apply_guided(1, answer, expected_question_version=None, now=c.now)
    return c
