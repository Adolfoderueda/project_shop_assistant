from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dialogue import DIALOGUE_TTL, DialogueMutation, LineRef
from domain import ListLine, Reply
from shopping_agent.contracts import (
    AgentProposal,
    AgentRunResult,
    AgentSnapshot,
    CompleteProposal,
    ItemInput,
    ItemPatch,
    ProposalDecision,
    ProposalItem,
    ProposeAdds,
    ProposeChange,
    Reservation,
    ToolCall,
    ToolResult,
)


@pytest.mark.parametrize('quantity', [True, 1.5, 0, -1, 2**63])
def test_strict_quantities_and_arguments(quantity):
    for contract, kwargs in [
        (ItemInput, {'description': 'arroz'}),
        (ProposeChange, {'kind': 'increment', 'query': 'arroz'}),
        (ItemPatch, {'position': 1}),
        (ProposalItem, {'position': 1, 'kind': 'add', 'description': 'arroz'}),
    ]:
        with pytest.raises(ValidationError):
            contract(**kwargs, quantity=quantity)


@pytest.mark.parametrize('extra', ['confirmed', 'user_id', 'chat_id', 'sql', 'permissions'])
def test_model_arguments_cannot_supply_authority(extra):
    for contract, kwargs in [
        (ItemInput, {'description': 'arroz'}),
        (ProposeAdds, {'items': (ItemInput(description='arroz'),)}),
        (ProposeChange, {'kind': 'set_quantity', 'query': 'arroz'}),
        (ItemPatch, {'position': 1}),
        (CompleteProposal, {'patches': ()}),
    ]:
        with pytest.raises(ValidationError):
            contract(**kwargs, **{extra: True})


def test_items_bounded_and_names_preserved():
    item = ItemInput(description='Blemil Evolution 1 800 g')
    assert item.quantity is None and item.unit is None
    assert item.description == 'Blemil Evolution 1 800 g'
    assert ItemInput(description='pañales talla 4').unit is None
    assert len(ProposeAdds(items=(item,) * 20).items) == 20
    for items in [(), (item,) * 21, [item]]:
        with pytest.raises(ValidationError):
            ProposeAdds(items=items)
    for description in ['', '   ', 'x' * 161]:
        with pytest.raises(ValidationError):
            ItemInput(description=description)
    assert ItemInput(description='x' * 160).description == 'x' * 160


@pytest.mark.parametrize('condition', ['', '   ', 'x' * 501])
def test_conditions_bounded(condition):
    with pytest.raises(ValidationError):
        ProposeAdds(items=(ItemInput(description='arroz'),), condition=condition)
    with pytest.raises(ValidationError):
        ProposeChange(kind='increment', query='arroz', condition=condition)


def test_replace_requires_exclusive_destination():
    assert ProposeChange(kind='replace', query='leche', replacement='leche de avena')
    for kwargs in [
        {'kind': 'replace', 'query': 'leche'},
        {'kind': 'increment', 'query': 'leche', 'replacement': 'avena'},
        {'kind': 'replace', 'query': 'leche', 'replacement': ' '},
        {'kind': 'set_quantity', 'query': ' '},
    ]:
        with pytest.raises(ValidationError):
            ProposeChange(**kwargs)


@pytest.mark.parametrize('position', [True, 0, -1, 21, 1.5])
def test_patch_position_is_bounded(position):
    with pytest.raises(ValidationError):
        ItemPatch(position=position)


def test_patch_selection_and_duplicate_decisions():
    assert ItemPatch(position=20, candidate_index=1, duplicate_decision='separate')
    assert ItemPatch(position=1, duplicate_decision='set_total', quantity=2)
    for kwargs in [{'candidate_index': 0}, {'candidate_index': True},
                   {'duplicate_decision': 'merge'}]:
        with pytest.raises(ValidationError):
            ItemPatch(position=1, **kwargs)
    with pytest.raises(ValidationError):
        CompleteProposal(patches=(ItemPatch(position=1), ItemPatch(position=1)))


def proposal(**overrides):
    now = datetime(2026, 10, 8, tzinfo=UTC)
    data = {'id': uuid4(), 'revision': 1, 'user_id': 123, 'chat_id': 456,
            'source_update_id': 7, 'original_text': 'añade arroz',
            'items': (ProposalItem(position=1, kind='add', description='arroz', quantity=2),),
            'updated_at': now, 'expires_at': now + DIALOGUE_TTL}
    return AgentProposal(**(data | overrides))


def test_review_requires_complete_unconditional_current_revision():
    assert proposal(reviewed_revision=1, reviewed_update_id=8).reviewed_revision == 1
    for overrides in [
        {'items': (ProposalItem(position=1, kind='add', description='arroz'),)},
        {'condition': 'si está en oferta'},
        {'reviewed_revision': 2},
        {'items': (ProposalItem(position=1, kind='increment', description='arroz', quantity=2),)},
        {'items': (ProposalItem(position=1, kind='add', description='arroz', quantity=2,
                               candidates=(LineRef(id='l1', revision=1),)),)},
    ]:
        with pytest.raises(ValidationError):
            proposal(**({'reviewed_revision': 1, 'reviewed_update_id': 8} | overrides))
    with pytest.raises(ValidationError):
        proposal(reviewed_revision=1)
    with pytest.raises(ValidationError):
        proposal(revision=True)
    with pytest.raises(ValidationError):
        proposal(schema_version=True)


def test_snapshot_context_omits_identity_but_keeps_application_data():
    snapshot = AgentSnapshot(
        proposal=proposal(), lines=(ListLine(id='l1', description='arroz', quantity=3, revision=2),),
        reservations=(Reservation(line_id='l1', order_id='o1'),),
        user_id=123, chat_id=456, source_update_id=9, original_text='qué lista tengo',
    )
    context = snapshot.model_context()
    assert context['lines'][0]['revision'] == 2
    assert context['reservations'] == [{'line_id': 'l1', 'order_id': 'o1'}]
    assert context['original_text'] == 'qué lista tengo'
    assert 'user_id' not in context and 'chat_id' not in context
    assert 'user_id' not in context['proposal'] and 'chat_id' not in context['proposal']
    assert context['proposal']['items'][0]['quantity'] == 2


def test_only_explicit_confirmation_decision_can_mutate():
    mutation = DialogueMutation(kind='add', description='arroz', quantity=2)
    assert ProposalDecision(reason='confirmed', mutations=(mutation,)).mutations == (mutation,)
    assert ProposalDecision(reason='pending').mutations == ()
    with pytest.raises(ValidationError):
        ProposalDecision(reason='pending', mutations=(mutation,))


def test_tool_and_run_envelopes_are_strict():
    reply = Reply(text='Propuesta pendiente')
    assert ToolCall(name='consultar_lista', arguments={}).arguments == {}
    assert ToolResult(name='consultar_lista', data={}, reply=reply, terminal=True).terminal
    assert AgentRunResult(reply=reply, model_calls=1, tool_calls=0, reason='terminal')
    with pytest.raises(ValidationError):
        AgentRunResult(reply=reply, model_calls=-1, tool_calls=0, reason='terminal')
    with pytest.raises(ValidationError):
        ToolResult(name='x', data={}, reply=reply, terminal=1)


def test_proposal_json_round_trip_and_lifetime():
    saved = proposal()
    assert AgentProposal.model_validate_json(saved.model_dump_json()) == saved
    assert ItemInput(description='arroz', quantity=2**63 - 1).quantity == 2**63 - 1
    with pytest.raises(ValidationError):
        saved.revision = 2
    with pytest.raises(ValidationError):
        proposal(expires_at=saved.updated_at)
    with pytest.raises(ValidationError):
        proposal(expires_at=saved.updated_at + DIALOGUE_TTL * 2)
    with pytest.raises(ValidationError):
        proposal(items=saved.items * 2)


def test_reviewed_increment_requires_coherent_arithmetic():
    target = LineRef(id='l1', revision=2)
    item = ProposalItem(position=1, kind='increment', description='arroz', quantity=5,
                        target=target, base_quantity=3, additional_quantity=2)
    assert proposal(items=(item,), reviewed_revision=1, reviewed_update_id=9)
    with pytest.raises(ValidationError):
        proposal(items=(item.model_copy(update={'quantity': 4}),),
                 reviewed_revision=1, reviewed_update_id=9)


def test_reviewed_replacement_requires_destination_and_duplicate_choice():
    item = ProposalItem(position=1, kind='replace', description='leche entera', quantity=2,
                        replacement='leche de avena', target=LineRef(id='l1', revision=1),
                        candidates=(LineRef(id='l2', revision=3),))
    with pytest.raises(ValidationError):
        proposal(items=(item,), reviewed_revision=1, reviewed_update_id=9)
    resolved = item.model_copy(update={'duplicate_decision': 'set_total'})
    assert proposal(items=(resolved,), reviewed_revision=1, reviewed_update_id=9)
    with pytest.raises(ValidationError):
        proposal(items=(resolved.model_copy(update={'replacement': None}),),
                 reviewed_revision=1, reviewed_update_id=9)


def test_duplicate_total_requires_selected_target_before_review():
    item = ProposalItem(position=1, kind='add', description='arroz', quantity=2,
                        candidates=(LineRef(id='l1', revision=1),),
                        duplicate_decision='set_total')
    with pytest.raises(ValidationError):
        proposal(items=(item,), reviewed_revision=1, reviewed_update_id=9)
    assert proposal(items=(item.model_copy(update={'target': item.candidates[0]}),),
                    reviewed_revision=1, reviewed_update_id=9)
    assert proposal(items=(item.model_copy(update={'duplicate_decision': 'separate'}),),
                    reviewed_revision=1, reviewed_update_id=9)
