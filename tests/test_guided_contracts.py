"""Boundary tests catch lost legacy data and accidental model/control authority."""

import json
from datetime import timedelta
from uuid import UUID

import pytest

from dialogue import DIALOGUE_TTL, DialogueMutation
from domain import IncomingCallback, InlineButton, InlineKeyboard, Reply, decode_event
from shopping_agent.contracts import (
    AgentProposal,
    AgentSnapshot,
    Contribution,
    GuidedProposal,
    ItemInput,
    ItemPatch,
    ProposalDecision,
    ProposeAdds,
    ReviewWitness,
    decode_proposal,
)
from shopping_agent.guided_contracts import (
    ChangeCandidate,
    Choice,
    ControlCandidate,
    GuidedDecision,
    GuidedModelResult,
    GuidedQuestion,
    GuidedState,
    PendingTopic,
    QuantityCandidate,
    ReadCandidate,
    ResolvedChoice,
    ScopeCandidate,
    TopicCandidate,
    decode_guided_answer,
)
from tests.guided_helpers import NOW, VALID_TOKEN, callback, message, state_fixture

V1 = '''{"id":"00000000-0000-0000-0000-000000000001","revision":1,
"user_id":7,"chat_id":7,"source_update_id":1,"original_text":"sí todos",
"items":[{"position":1,"kind":"add","description":"sí","quantity":2}],
"updated_at":"2026-10-09T00:00:00Z","expires_at":"2026-10-09T00:15:00Z",
"reviewed_revision":1,"reviewed_update_id":2}'''
QUESTION_ID = UUID('00000000-0000-0000-0000-000000000002')


def question(**overrides):
    proposal = state_fixture().snapshot.proposal
    data = {'id': QUESTION_ID, 'version': 1, 'owner_id': 7, 'chat_id': 7, 'kind': 'scope',
            'proposal_id': proposal.id, 'proposal_revision': 1, 'positions': (1, 2, 3),
            'choices': (Choice(kind='choose_scope', label='Todos', positions=(1, 2, 3)),),
            'source_update_id': 1, 'created_at': NOW, 'expires_at': NOW + DIALOGUE_TTL,
            'status': 'active', 'text': '¿Para cuáles?', 'candidate': None}
    return GuidedQuestion(**(data | overrides))


def witness(**overrides):
    data = {'proposal_id': state_fixture().snapshot.proposal.id, 'revision': 1,
            'question_id': QUESTION_ID, 'summary_digest': 'a' * 64, 'source_update_id': 2,
            'notice_id': 'notice', 'delivered_message_id': None}
    return ReviewWitness(**(data | overrides))


def test_old_reply_and_message_remain_readable():
    assert Reply.model_validate_json('{"text":"pendiente"}').keyboard is None
    assert Reply(text='pendiente').model_dump_json() == '{"text":"pendiente","order_id":null}'
    assert decode_event({'update_id': 1, 'user_id': 7, 'chat_id': 7, 'text': 'sí'}) == message(1, 'sí')
    assert message(1, '').model_dump() == {'update_id': 1, 'user_id': 7, 'chat_id': 7, 'text': ''}
    assert decode_event(message(1, '').model_dump()) == message(1, '')


def test_callbacks_require_explicit_kind_and_strict_authenticated_fields():
    event = callback(2, VALID_TOKEN)
    assert decode_event(event.model_dump()) == event
    assert isinstance(decode_event(event.model_dump()), IncomingCallback)
    for changes in ({'kind': 'message'}, {'kind': None}, {'user_id': True}, {'text': ''}):
        with pytest.raises(ValueError):
            decode_event(event.model_dump() | changes)
    payload = event.model_dump()
    del payload['kind']
    with pytest.raises(ValueError):
        decode_event(payload)


@pytest.mark.parametrize('token', ['', 'q:' + 'A' * 21, 'q:' + 'A' * 23,
                                   'q:' + 'é' * 22, 'q:' + '+' * 22, 'confirm'])
def test_callback_and_button_reject_malformed_tokens(token):
    with pytest.raises(ValueError):
        callback(2, token)
    with pytest.raises(ValueError):
        InlineButton(label='Sí', token=token)


def test_keyboard_roundtrip_preserves_rows_and_24_byte_tokens():
    button = InlineButton(label='Sí', token=VALID_TOKEN)
    assert len(button.token.encode('ascii')) == 24
    reply = Reply(text='Elige', keyboard=InlineKeyboard(rows=(
        (button, InlineButton(label='No', token='q:' + '_' * 22)), (button,))))
    restored = Reply.model_validate_json(reply.model_dump_json())
    assert [[b.label for b in row] for row in restored.keyboard.rows] == [['Sí', 'No'], ['Sí']]
    with pytest.raises(ValueError):
        button.label = 'No'


def test_v1_literal_keeps_old_review_without_v2_contributions():
    proposal = decode_proposal(V1)
    assert type(proposal) is AgentProposal
    assert proposal.reviewed_revision == 1 and proposal.reviewed_update_id == 2
    assert 'contributions' not in proposal.model_dump()
    assert decode_proposal(proposal.model_dump_json()) == proposal
    with pytest.raises(ValueError):
        decode_proposal(json.dumps(json.loads(V1) | {'contributions': []}))


def test_v2_roundtrip_in_snapshot_and_decision():
    proposal = state_fixture().snapshot.proposal
    assert decode_proposal(proposal.model_dump_json()) == proposal
    snapshot = state_fixture().snapshot
    assert AgentSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    assert ProposalDecision(proposal=proposal, reason='pending').proposal == proposal


@pytest.mark.parametrize('changes', [
    {'source_update_id': True}, {'source_update_id': -1},
    {'contributions': []}, {'contributions': [{'update_id': True, 'positions': [1], 'kind': 'create'}]},
    {'contributions': [{'update_id': -1, 'positions': [1], 'kind': 'create'}]},
    {'contributions': [{'update_id': 1, 'positions': [4], 'kind': 'create'}]},
    {'contributions': [{'update_id': 1, 'positions': [1, 1], 'kind': 'create'}]},
    {'schema_version': True}, {'schema_version': 3},
    {'review': {'proposal_id': '00000000-0000-0000-0000-000000000001', 'revision': 1}},
])
def test_v2_rejects_invalid_provenance_and_incomplete_witness(changes):
    with pytest.raises(ValueError):
        decode_proposal(json.dumps(state_fixture().snapshot.proposal.model_dump(mode='json') | changes))


@pytest.mark.parametrize('payload', [{'kind': 'confirm'}, {'kind': 'save'},
                                   {'kind': 'cancel', 'user_id': 7},
                                   {'kind': 'clarify', 'source_update_id': 1},
                                   {'kind': 'quantity', 'patches': [], 'source_update_id': 1}])
def test_model_answer_cannot_confirm_or_save(payload):
    with pytest.raises(ValueError):
        decode_guided_answer(payload)


def test_product_control_words_are_data():
    answer = decode_guided_answer({'kind': 'topic', 'source_update_id': 3,
                                  'adds': {'items': [{'description': 'sí'}, {'description': 'todos'}]}})
    assert isinstance(answer, TopicCandidate)
    assert [i.description for i in answer.adds.items] == ['sí', 'todos']
    assert decode_guided_answer({'kind': 'quantity', 'source_update_id': 3,
                                 'patches': [{'position': 1, 'quantity': 2}]}) == QuantityCandidate(
                                     source_update_id=3, patches=(ItemPatch(position=1, quantity=2),))
    assert isinstance(decode_guided_answer({'kind': 'scope', 'positions': [1],
                                          'source_update_id': 3}), ScopeCandidate)
    assert isinstance(decode_guided_answer({'kind': 'change', 'source_update_id': 3,
                    'change': {'kind': 'set_quantity', 'query': 'todos', 'quantity': 2}}), ChangeCandidate)
    assert isinstance(decode_guided_answer({'kind': 'list'}), ReadCandidate)
    assert decode_guided_answer({'kind': 'fiche'}).query is None
    assert decode_guided_answer({'kind': 'fiche', 'query': 'todos'}).query == 'todos'
    assert isinstance(decode_guided_answer({'kind': 'cancel'}), ControlCandidate)
    assert isinstance(decode_guided_answer({'kind': 'clarify'}), ControlCandidate)


@pytest.mark.parametrize('payload', [
    {'kind': 'scope', 'positions': [True], 'source_update_id': 1},
    {'kind': 'scope', 'positions': [1, 1], 'source_update_id': 1},
    {'kind': 'quantity', 'patches': [{'position': 1, 'quantity': True}], 'source_update_id': 1},
    {'kind': 'quantity', 'patches': [{'position': True, 'quantity': 1}], 'source_update_id': 1},
    {'kind': 'quantity', 'patches': [{'position': 1}, {'position': 1}], 'source_update_id': 1},
    {'kind': 'list', 'user_id': 7}, {'kind': 'fiche', 'query': True},
])
def test_candidates_reject_invalid_positions_quantities_and_read_combinations(payload):
    with pytest.raises(ValueError):
        decode_guided_answer(payload)


@pytest.mark.parametrize('kwargs', [
    {'kind': 'confirm', 'positions': (1,)}, {'kind': 'cancel', 'unit': 'pack'},
    {'kind': 'choose_scope'}, {'kind': 'choose_unit'},
    {'kind': 'choose_line', 'positions': (1,), 'candidate_index': True},
    {'kind': 'choose_line', 'positions': (1, 2), 'candidate_index': 1},
    {'kind': 'one_each', 'candidate_index': 1}, {'kind': 'choose_scope', 'positions': (1, 1)},
])
def test_choice_rejects_incompatible_data(kwargs):
    with pytest.raises(ValueError):
        Choice(label='Aplicación', **kwargs)


def test_question_enforces_versions_ttl_and_offered_positions():
    assert question().kind == 'scope'
    for changes in ({'version': True}, {'version': 0}, {'proposal_revision': 0},
                    {'expires_at': NOW}, {'expires_at': NOW + DIALOGUE_TTL * 2},
                    {'choices': (Choice(kind='choose_scope', label='Otro', positions=(4,)),)},
                    {'positions': (1, 1)},
                    {'candidate': QuantityCandidate(source_update_id=1,
                                                   patches=(ItemPatch(position=4, quantity=2),))}):
        with pytest.raises(ValueError):
            question(**changes)
    state = state_fixture()
    q = question(expires_at=NOW + DIALOGUE_TTL)
    later_snapshot = state.snapshot.model_copy(update={'source_update_id': 2})
    # A question may be loaded after expiry: time-based consumption belongs to the reducer.
    assert GuidedState(snapshot=later_snapshot, question=q, topic=None, review=None).question == q
    shortened = state.snapshot.proposal.model_copy(update={'expires_at': NOW + timedelta(minutes=1)})
    with pytest.raises(ValueError):
        GuidedState(snapshot=state.snapshot.model_copy(update={'proposal': shortened}),
                    question=q, topic=None, review=None)


def reviewed_state(delivered=None):
    state = state_fixture(quantities=(1, 2, 3))
    review = witness(delivered_message_id=delivered)
    proposal = GuidedProposal.model_validate(state.snapshot.proposal.model_dump() | {'review': review})
    return GuidedState(snapshot=state.snapshot.model_copy(update={'proposal': proposal}),
                       question=question(kind='review', choices=(Choice(kind='confirm', label='Confirmar'),)),
                       topic=None, review=review)


def test_review_projection_and_mutation_require_current_delivered_witness():
    mutation = DialogueMutation(kind='add', description='huevos', quantity=1)
    delivered = reviewed_state(100)
    assert GuidedDecision(state=delivered, reply=Reply(text='Guardado'), reason='confirmed',
                          mutations=(mutation,)).mutations == (mutation,)
    for state, reason in [(reviewed_state(), 'confirmed'), (state_fixture(), 'confirmed'),
                          (delivered, 'pending')]:
        with pytest.raises(ValueError):
            GuidedDecision(state=state, reply=Reply(text='No'), reason=reason, mutations=(mutation,))
    with pytest.raises(ValueError):
        GuidedState(snapshot=delivered.snapshot, question=delivered.question, topic=None, review=None)
    for changes in ({'revision': 2}, {'proposal_id': QUESTION_ID}):
        with pytest.raises(ValueError):
            GuidedProposal.model_validate(delivered.snapshot.proposal.model_dump() |
                                          {'review': witness(**changes)})
    with pytest.raises(ValueError):
        GuidedProposal.model_validate(state_fixture().snapshot.proposal.model_dump() |
                                      {'review': witness()})


@pytest.mark.parametrize('status', ['expired', 'revoked'])
def test_mutations_cannot_use_invalidated_review_question(status):
    state = reviewed_state(100)
    state = GuidedState(snapshot=state.snapshot, review=state.review,
                        question=state.question.model_copy(update={'status': status}))
    with pytest.raises(ValueError):
        GuidedDecision(state=state, reply=Reply(text='No'), reason='confirmed',
                       mutations=(DialogueMutation(kind='add', description='huevos', quantity=1),))


def test_pending_topic_preserves_condition_and_binds_revision():
    proposal = state_fixture().snapshot.proposal
    topic = PendingTopic(id=QUESTION_ID, version=1, source_update_id=3, original_text='sí',
                         items=(ItemInput(description='sí'),), condition='si está en oferta',
                         proposal_id=proposal.id, proposal_revision=1, expires_at=proposal.expires_at)
    state = GuidedState(snapshot=state_fixture().snapshot, question=None, topic=topic, review=None)
    assert GuidedState.model_validate_json(state.model_dump_json()).topic.condition == 'si está en oferta'
    with pytest.raises(ValueError):
        GuidedState(snapshot=state.snapshot, question=None,
                    topic=topic.model_copy(update={'proposal_revision': 2}), review=None)


def test_application_envelopes_and_contributions_are_strict():
    assert ResolvedChoice(question_id=QUESTION_ID, question_version=1, choice_index=0, source_update_id=2)
    assert GuidedModelResult(answer=None, reason='invalid', model_calls=0, tool_calls=0)
    for kwargs in ({'model_calls': True}, {'model_calls': 5}, {'tool_calls': 9}, {'reply': Reply(text='x')}):
        with pytest.raises(ValueError):
            GuidedModelResult(**({'answer': None, 'reason': 'invalid', 'model_calls': 0,
                                  'tool_calls': 0} | kwargs))
    with pytest.raises(ValueError):
        Contribution(update_id=1, positions=(1,), kind='create', user_id=7)
    with pytest.raises(ValueError):
        ResolvedChoice(question_id=QUESTION_ID, question_version=1, choice_index=True, source_update_id=2)
    with pytest.raises(ValueError):
        ProposeAdds(items=(ItemInput(description='x'),) * 21)


@pytest.mark.parametrize('changes', [
    {'delivered_message_id': True}, {'delivered_message_id': 0},
    {'source_update_id': True}, {'source_update_id': -1},
    {'revision': True}, {'summary_digest': ''},
])
def test_witness_rejects_invalid_delivery_and_source(changes):
    with pytest.raises(ValueError):
        witness(**changes)


def test_guided_state_rejects_proposal_from_another_owner_or_chat():
    state = state_fixture()
    for changes in ({'user_id': 8}, {'chat_id': 8}):
        with pytest.raises(ValueError):
            GuidedState(snapshot=state.snapshot.model_copy(update=changes))


def test_historical_snapshot_without_explicit_schema_remains_readable():
    payload = {'proposal': json.loads(V1), 'user_id': 7, 'chat_id': 7,
               'source_update_id': 3, 'original_text': 'lista'}
    snapshot = AgentSnapshot.model_validate_json(json.dumps(payload))
    assert type(snapshot.proposal) is AgentProposal
    assert snapshot.proposal.reviewed_update_id == 2


def test_question_keeps_unapplied_candidate_and_rejects_invalid_ownership():
    candidate = QuantityCandidate(source_update_id=2, patches=(ItemPatch(position=1, quantity=4),))
    state = GuidedState(snapshot=state_fixture().snapshot, question=question(candidate=candidate))
    assert state.snapshot.proposal.items[0].quantity is None
    assert GuidedState.model_validate_json(state.model_dump_json()).question.candidate == candidate
    for changes in ({'owner_id': 8}, {'chat_id': 8}, {'proposal_revision': 2}):
        with pytest.raises(ValueError):
            GuidedState(snapshot=state.snapshot, question=question(**changes))


@pytest.mark.parametrize('kwargs', [
    {'kind': 'one_each', 'positions': (1, 2, 3)},
    {'kind': 'same_quantity', 'positions': (1, 2)},
    {'kind': 'different_quantities'}, {'kind': 'write_answer'},
    {'kind': 'choose_scope', 'positions': (2,)},
    {'kind': 'choose_unit', 'unit': 'paquetes', 'positions': (1,)},
    {'kind': 'separate', 'positions': (1,)}, {'kind': 'set_total', 'positions': (1,)},
    {'kind': 'choose_line', 'positions': (1,), 'candidate_index': 1},
    {'kind': 'remove_condition'}, {'kind': 'append_topic'}, {'kind': 'keep_topic'},
    {'kind': 'confirm'}, {'kind': 'correct'}, {'kind': 'cancel'},
])
def test_valid_application_choices_are_preserved(kwargs):
    choice = Choice(label='Aplicación', **kwargs)
    assert Choice.model_validate_json(choice.model_dump_json()) == choice
