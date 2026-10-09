"""Independent transition oracles: candidates never grant write authority."""

from datetime import timedelta

import pytest

from shopping_agent.contracts import (
    ItemInput,
    ItemPatch,
    ProposalItem,
    ProposeAdds,
    Reservation,
)
from shopping_agent.guided_contracts import (
    ControlCandidate,
    QuantityCandidate,
    ReadCandidate,
    ResolvedChoice,
    ScopeCandidate,
    TopicCandidate,
)
from shopping_agent.guided_controller import next_question, reduce_guided, resolve_text_choice
from tests.guided_helpers import (
    NOW,
    VALID_TOKEN,
    callback,
    candidate,
    increment_state,
    message,
    state_fixture,
    topic_state_fixture,
    with_items,
)


def start(state=None):
    state = state or state_fixture()
    return reduce_guided(state, message(2, 'cantidades'), None, now=NOW).state


def select(state, label, update=3):
    event = message(update, label)
    choice = resolve_text_choice(event, state.question)
    assert choice is not None
    return reduce_guided(state, event, choice, now=NOW)


def quantities(state):
    return tuple(item.quantity for item in state.snapshot.proposal.items)


def test_candidate_does_not_grant_unselected_collective_scope():
    state = state_fixture()
    decision = reduce_guided(state, message(2, 'Pon uno'), candidate(2, (1, 1)), now=NOW)
    assert quantities(decision.state) == (None, None, None)
    assert decision.state.question.kind == 'scope'
    assert decision.state.question.candidate.source_update_id == 2
    assert decision.mutations == ()


def test_one_each_is_draft_only_and_consumes_question_version():
    state = start()
    decision = select(state, 'Uno de cada')
    assert quantities(decision.state) == (1, 1, 1)
    assert decision.state.question.kind == 'review'
    assert decision.state.question.version == state.question.version + 1
    assert decision.state.review.delivered_message_id is None
    assert decision.mutations == ()


def test_shared_selection_then_quantity():
    state = select(start(), 'Misma cantidad').state
    assert state.question.kind == 'quantity_shared'
    decision = reduce_guided(state, message(4, 'dos'), candidate(4, (1, 2)), now=NOW)
    assert quantities(decision.state) == (2, 2, 2)
    assert decision.mutations == ()


def test_individual_selection_preserves_answers_and_advances():
    state = select(start(), 'Cantidades diferentes').state
    assert state.question.positions == (1,)
    decision = reduce_guided(state, message(4, 'dos'), candidate(4, (1, 2)), now=NOW)
    assert quantities(decision.state) == (2, None, None)
    assert decision.state.question.kind == 'quantity_single'
    assert decision.state.question.positions == (2,)


def test_candidate_applied_only_to_explicitly_selected_scope():
    state = reduce_guided(state_fixture(), message(2, 'uno'), candidate(2, (1, 1)), now=NOW).state
    decision = select(state, 'carne')
    assert quantities(decision.state) == (None, 1, None)
    assert decision.state.snapshot.proposal.contributions[-2].update_id == 2
    assert decision.state.snapshot.proposal.contributions[-1].update_id == 3


def test_correction_of_complete_item_requires_scope_and_revokes_review():
    state = start(state_fixture(quantities=(1, 1, 1)))
    state = reduce_guided(state, message(3, 'sí, pero carne dos'), candidate(3, (2, 2)), now=NOW).state
    assert quantities(state) == (1, 1, 1)
    assert state.review is None
    decision = select(state, 'carne', 4)
    assert quantities(decision.state) == (1, 2, 1)
    assert decision.state.question.kind == 'review'
    assert decision.mutations == ()


def test_yes_during_scope_never_confirms():
    state = start()
    assert resolve_text_choice(message(3, 'sí'), state.question) is None
    decision = reduce_guided(state, message(3, 'sí'), None, now=NOW)
    assert decision.state == state
    assert decision.mutations == ()


def test_condition_persists_until_explicit_removal():
    state = start(state_fixture(quantities=(1, 1, 1), condition='si hay oferta'))
    assert state.question.kind == 'condition'
    assert reduce_guided(state, message(3, 'sí'), None, now=NOW).state == state
    decision = select(state, 'Retirar condición')
    assert decision.state.snapshot.proposal.condition is None
    assert decision.state.question.kind == 'review'


def test_keep_topic_does_not_cancel_main_draft():
    state = topic_state_fixture()
    decision = reduce_guided(state, message(4, 'no'), None, now=NOW)
    assert decision.state.topic is None
    assert tuple(i.description for i in decision.state.snapshot.proposal.items) == ('huevos', 'carne', 'atun')
    assert decision.state.question.kind == 'review'
    assert decision.mutations == ()


def test_append_preserves_id_positions_and_origin():
    state = topic_state_fixture()
    before = state.snapshot.proposal
    decision = select(state, 'Añadir al borrador', 4)
    after = decision.state.snapshot.proposal
    assert after.id == before.id
    assert after.items[:3] == before.items
    assert after.items[3].position == 4
    assert after.contributions[-2].update_id == 3
    assert after.contributions[-2].positions == (4,)
    assert after.contributions[-2].kind == 'append'
    assert after.contributions[-1].update_id == 4
    assert after.original_text == before.original_text
    assert decision.state.topic is None
    assert decision.mutations == ()


def test_other_request_does_not_replace_pending_topic():
    state = topic_state_fixture()
    decision = reduce_guided(state, message(4, 'pan'), TopicCandidate(source_update_id=4,
        adds=ProposeAdds(items=(ItemInput(description='pan'),))), now=NOW)
    assert decision.state == state
    assert 'pendiente' in decision.reply.text


def test_expiry_and_read_do_not_renew_question():
    state = start()
    decision = reduce_guided(state, message(3, 'sí'), None, now=NOW + timedelta(minutes=16))
    assert decision.state == state
    assert decision.reason == 'expired'
    assert decision.mutations == ()


@pytest.mark.parametrize('field,value', [('question_version', 100), ('choice_index', 100)])
def test_stale_or_unoffered_choice_fails_closed(field, value):
    state = start()
    choice = ResolvedChoice(question_id=state.question.id, question_version=state.question.version,
                           choice_index=0, source_update_id=3)
    choice = choice.model_copy(update={field: value})
    assert reduce_guided(state, message(3, 'x'), choice, now=NOW).state == state


def test_question_ids_are_deterministic_for_replay():
    state = state_fixture()
    assert next_question(state, message(2, 'x'), now=NOW) == next_question(state, message(2, 'x'), now=NOW)


def test_nineteen_plus_two_preserves_both_states_without_truncation():
    state = with_items(tuple(ProposalItem(position=i, kind='add', description=f'producto {i}', quantity=1)
                             for i in range(1, 20)))
    state = reduce_guided(state, message(2, 'leche y pan'), TopicCandidate(source_update_id=2,
        adds=ProposeAdds(items=(ItemInput(description='leche'), ItemInput(description='pan')))), now=NOW).state
    decision = select(state, 'Añadir al borrador')
    assert decision.state == state
    assert decision.reason == 'too_many'
    assert len(decision.state.snapshot.proposal.items) == 19
    assert len(decision.state.topic.items) == 2


def test_append_recomputes_conflicts_for_both_elements():
    state = start(state_fixture(quantities=(1, 1, 1)))
    state = reduce_guided(state, message(3, 'más huevos'), TopicCandidate(source_update_id=3,
        adds=ProposeAdds(items=(ItemInput(description='huevos', quantity=2),))), now=NOW).state
    decision = select(state, 'Añadir al borrador', 4)
    assert decision.state.snapshot.proposal.items[0].internal_conflicts == (4,)
    assert decision.state.snapshot.proposal.items[3].internal_conflicts == (1,)
    assert quantities(decision.state) == (1, 1, 1, 2)
    assert decision.state.question.kind == 'duplicate'
    assert decision.state.review is None


def test_each_append_has_its_original_source_update():
    state = select(topic_state_fixture(), 'Añadir al borrador', 4).state
    state = reduce_guided(state, message(5, 'pan'), TopicCandidate(source_update_id=5,
        adds=ProposeAdds(items=(ItemInput(description='pan'),))), now=NOW).state
    state = select(state, 'Añadir al borrador', 6).state
    assert [(c.update_id, c.positions) for c in state.snapshot.proposal.contributions if c.kind == 'append'] == [
        (3, (4,)), (5, (5,))]


def test_required_diaper_unit_even_when_quantity_complete():
    state = with_items((ProposalItem(position=1, kind='add', description='pañales', quantity=1),))
    state = start(state)
    assert state.question.kind == 'unit'
    decision = select(state, 'paquetes')
    assert decision.state.snapshot.proposal.items[0].unit == 'paquetes'
    assert decision.state.question.kind == 'review'


def test_control_named_product_does_not_shadow_choice():
    state = with_items((ProposalItem(position=1, kind='add', description='no'),
                        ProposalItem(position=2, kind='add', description='confirmar')))
    state = reduce_guided(state, message(2, 'uno'), candidate(2, (1, 1)), now=NOW).state
    choice = resolve_text_choice(message(3, 'no'), state.question)
    assert state.question.choices[choice.choice_index].kind == 'choose_scope'
    assert state.question.choices[choice.choice_index].positions == (1,)
    assert quantities(reduce_guided(state, message(3, 'no'), choice, now=NOW).state) == (1, None)


def test_read_preserves_question_topic_and_expiry():
    state = topic_state_fixture()
    decision = reduce_guided(state, message(4, 'lista'), ReadCandidate(kind='list'), now=NOW + timedelta(minutes=1))
    assert decision.state == state
    assert decision.reason == 'read'


def test_review_requires_delivery_and_current_digest_then_confirms():
    state = start(state_fixture(quantities=(1, 2, 3)))
    assert select(state, 'sí', 3).mutations == ()
    witness = state.review.model_copy(update={'delivered_message_id': 100})
    state = state.model_copy(update={'review': witness, 'snapshot': state.snapshot.model_copy(update={
        'proposal': state.snapshot.proposal.model_copy(update={'review': witness})})})
    decision = select(state, 'sí', 3)
    assert tuple(m.quantity for m in decision.mutations) == (1, 2, 3)
    assert decision.reason == 'confirmed'
    assert select(state, 'sí', 2).mutations == ()
    bad = witness.model_copy(update={'summary_digest': 'wrong'})
    invalid = state.model_copy(update={'review': bad, 'snapshot': state.snapshot.model_copy(update={
        'proposal': state.snapshot.proposal.model_copy(update={'review': bad})})})
    assert select(invalid, 'sí', 3).mutations == ()


def test_unknown_base_is_not_zero_and_needs_explicit_total():
    state = start(increment_state(base=None))
    assert state.snapshot.proposal.items[0].quantity is None
    assert state.question.kind == 'duplicate'
    assert 'no es cero' in state.question.text
    state = select(state, 'Cambiar cantidad total').state
    assert state.question.kind == 'quantity_single'
    decision = reduce_guided(state, message(4, 'cinco'), candidate(4, (1, 5)), now=NOW)
    assert decision.state.snapshot.proposal.items[0].kind == 'set_quantity'
    assert decision.state.snapshot.proposal.items[0].quantity == 5


def test_reserved_source_is_not_offered_or_selected():
    state = start(increment_state(reserved=True, selected=False))
    assert state.question is None
    assert state.review is None
    assert state.snapshot.proposal.items[0].target is None
    assert state.snapshot.proposal.items[0].quantity is None


def test_reserved_selected_row_cannot_enable_review():
    state = start(increment_state(reserved=True))
    assert state.question is None
    assert state.review is None


def test_only_single_position_context_grants_quantity_authority_without_choice():
    state = with_items((ProposalItem(position=1, kind='add', description='leche'),))
    decision = reduce_guided(state, message(2, 'dos'), candidate(2, (1, 2)), now=NOW)
    assert quantities(decision.state) == (2,)
    assert decision.state.question.kind == 'review'


def test_write_answer_keeps_selected_shared_focus():
    state = select(start(), 'Misma cantidad').state
    changed = select(state, 'Escribir respuesta', 4).state
    assert changed.question.kind == 'quantity_shared'
    assert changed.question.positions == (1, 2, 3)
    assert changed.question.version == state.question.version + 1
    assert quantities(reduce_guided(changed, message(5, 'dos'), candidate(5, (1, 2)), now=NOW).state) == (2, 2, 2)


def test_scope_model_candidate_is_selection_question_not_authority():
    decision = reduce_guided(start(), message(3, 'la carne'),
        ScopeCandidate(positions=(2,), source_update_id=3), now=NOW)
    assert quantities(decision.state) == (None, None, None)
    assert any(choice.kind == 'choose_scope' and choice.positions == (2,)
               for choice in decision.state.question.choices)


def test_new_reservation_rejects_previously_offered_source_without_edit():
    state = start(increment_state(selected=False))
    state = state.model_copy(update={'snapshot': state.snapshot.model_copy(update={
        'reservations': (Reservation(line_id='line', order_id='order'),)})})
    decision = select(state, '1')
    assert decision.state == state
    assert decision.reason == 'reserved'
    assert decision.mutations == ()


def test_increment_overflow_is_not_reviewed_and_explains_range():
    from dialogue import MAX_QUANTITY

    state = start(increment_state(base=MAX_QUANTITY - 3))
    state = select(state, 'Corregir', 3).state
    state = select(state, 'leche', 4).state
    decision = reduce_guided(state, message(5, 'cuatro'), candidate(5, (1, 4)), now=NOW)
    assert decision.state.review is None
    assert decision.reason == 'quantity_range'
    assert decision.state.snapshot.proposal.items[0].quantity is None
    assert decision.mutations == ()


def test_topic_no_is_not_model_authored_cancellation():
    state = topic_state_fixture()
    decision = reduce_guided(state, message(4, 'no'), ControlCandidate(kind='cancel'), now=NOW)
    assert decision.state.snapshot.proposal is not None
    assert decision.state.topic is None


def test_model_cannot_cancel_without_explicit_control():
    state = start()
    decision = reduce_guided(state, message(3, 'sí'), ControlCandidate(kind='cancel'), now=NOW)
    assert decision.state == state
    assert decision.mutations == ()


def test_callback_cannot_supply_model_authored_quantities():
    state = select(start(), 'Misma cantidad').state
    decision = reduce_guided(state, callback(4, VALID_TOKEN), candidate(4, (1, 2)), now=NOW)
    assert decision.state == state
    assert decision.mutations == ()


def test_quantity_one_is_not_a_menu_index():
    state = select(start(), 'Misma cantidad').state
    assert resolve_text_choice(message(4, '1'), state.question) is None


def test_question_identity_includes_successor_version():
    from uuid import NAMESPACE_URL, uuid5

    state = select(start(), 'Misma cantidad').state
    q = state.question
    assert q.id == uuid5(NAMESPACE_URL,
        f'guided:7:7:3:{q.proposal_id}:{q.proposal_revision}:{q.kind}:{q.version}')


def test_confirm_consumes_review_and_cannot_repeat_mutations():
    state = start(state_fixture(quantities=(1, 2, 3)))
    witness = state.review.model_copy(update={'delivered_message_id': 100})
    state = state.model_copy(update={'review': witness, 'snapshot': state.snapshot.model_copy(update={
        'proposal': state.snapshot.proposal.model_copy(update={'review': witness})})})
    decision = select(state, 'sí', 3)
    assert decision.state.question.status == 'consumed'
    assert reduce_guided(decision.state, message(4, 'sí'), None, now=NOW).mutations == ()


def test_shared_selection_is_preserved_as_application_contribution():
    state = select(start(), 'Misma cantidad').state
    assert state.snapshot.proposal.contributions[-1].update_id == 3
    assert state.snapshot.proposal.contributions[-1].kind == 'decision'
    assert state.snapshot.proposal.contributions[-1].positions == (1, 2, 3)


def test_review_cannot_be_confirmed_by_unoffered_numeric_index():
    state = start(state_fixture(quantities=(1, 1, 1)))
    assert resolve_text_choice(message(3, '1'), state.question) is None


def test_callback_selection_uses_same_pure_transition():
    state = start()
    choice = ResolvedChoice(question_id=state.question.id, question_version=state.question.version,
                            choice_index=0, source_update_id=3)
    decision = reduce_guided(state, callback(3, VALID_TOKEN), choice, now=NOW)
    assert quantities(decision.state) == (1, 1, 1)
    assert decision.state.question.kind == 'review'
    assert decision.mutations == ()


def test_new_topic_suspends_delivered_review():
    state = topic_state_fixture()
    assert state.review is None
    assert state.snapshot.proposal.review is None
    assert state.question.kind == 'topic'
    assert state.topic.original_text == 'leche'


def test_unauthorized_owner_cannot_select_or_edit():
    state = start()
    choice = ResolvedChoice(question_id=state.question.id, question_version=state.question.version,
                            choice_index=0, source_update_id=3)
    assert reduce_guided(state, message(3, 'x', owner=8), choice, now=NOW).state == state
    assert resolve_text_choice(message(3, 'Uno de cada', owner=8), state.question) is None


def test_condition_and_append_are_preserved_without_combining_different_conditions():
    state = start(state_fixture(condition='si hay oferta'))
    state = reduce_guided(state, message(3, 'leche si está fresca'), TopicCandidate(source_update_id=3,
        adds=ProposeAdds(items=(ItemInput(description='leche'),), condition='si está fresca')), now=NOW).state
    decision = select(state, 'Añadir al borrador', 4)
    assert decision.state == state
    assert decision.reason == 'condition'
    assert decision.state.snapshot.proposal.condition == 'si hay oferta'
    assert decision.state.topic.condition == 'si está fresca'


def test_condition_on_appended_topic_precedes_quantity_and_review():
    state = start(state_fixture(quantities=(1, 1, 1)))
    state = reduce_guided(state, message(3, 'leche si hay oferta'), TopicCandidate(source_update_id=3,
        adds=ProposeAdds(items=(ItemInput(description='leche'),), condition='si hay oferta')), now=NOW).state
    decision = select(state, 'Añadir al borrador', 4)
    assert decision.state.snapshot.proposal.condition == 'si hay oferta'
    assert decision.state.question.kind == 'condition'
    assert quantities(decision.state) == (1, 1, 1, None)


def test_internal_duplicates_require_decision_for_each_position():
    state = with_items((ProposalItem(position=1, kind='add', description='leche', quantity=1, internal_conflicts=(2,)),
                        ProposalItem(position=2, kind='add', description='leche', quantity=2, internal_conflicts=(1,))))
    state = start(state)
    assert state.question.positions == (1,)
    state = select(state, 'Añadir otra línea').state
    assert state.question.kind == 'duplicate'
    assert state.question.positions == (2,)
    state = select(state, 'Añadir otra línea', 4).state
    assert state.question.kind == 'review'
    assert quantities(state) == (1, 2)


def test_missing_increment_can_be_explicitly_separate_without_inventing_base():
    state = with_items((ProposalItem(position=1, kind='increment', description='leche', additional_quantity=3),))
    state = start(state)
    assert state.question.kind == 'duplicate'
    decision = select(state, 'Añadir otra línea')
    item = decision.state.snapshot.proposal.items[0]
    assert item.kind == 'add' and item.quantity == 3
    assert item.base_quantity is None and item.additional_quantity is None
    assert decision.state.question.kind == 'review'


def test_legacy_complete_proposal_can_receive_new_guided_review_without_fabricated_origin():
    from shopping_agent.contracts import AgentProposal

    state = state_fixture(quantities=(1, 1, 1))
    fields = state.snapshot.proposal.model_dump(exclude={'contributions', 'review'})
    fields['schema_version'] = 1
    proposal = AgentProposal.model_validate(fields)
    state = state.model_copy(update={'snapshot': state.snapshot.model_copy(update={'proposal': proposal})})
    decision = reduce_guided(state, message(2, 'revisar'), None, now=NOW)
    assert decision.state.review is not None
    assert decision.state.snapshot.proposal.original_text == proposal.original_text
    assert decision.state.snapshot.proposal.contributions[0].update_id == proposal.source_update_id
    assert decision.state.snapshot.proposal.expires_at == proposal.expires_at


def test_noop_quantity_candidate_preserves_entire_state():
    state = select(start(), 'Misma cantidad').state
    decision = reduce_guided(state, message(4, 'no sé'), QuantityCandidate(source_update_id=4,
        patches=(ItemPatch(position=1),)), now=NOW)
    assert decision.state == state


def test_different_candidate_quantities_require_individual_clarification():
    state = reduce_guided(state_fixture(), message(2, 'dos y tres'), candidate(2, (1, 2), (2, 3)), now=NOW).state
    state = select(state, 'Todos').state
    assert quantities(state) == (None, None, None)
    assert state.question.kind == 'quantity_single'
    assert state.question.positions == (1,)


def test_legacy_review_is_revoked_when_opening_topic():
    from shopping_agent.contracts import AgentProposal

    state = state_fixture(quantities=(1, 1, 1))
    fields = state.snapshot.proposal.model_dump(exclude={'contributions', 'review'})
    fields.update(schema_version=1, reviewed_revision=1, reviewed_update_id=1)
    proposal = AgentProposal.model_validate(fields)
    state = state.model_copy(update={'snapshot': state.snapshot.model_copy(update={'proposal': proposal})})
    decision = reduce_guided(state, message(2, 'leche'), TopicCandidate(source_update_id=2,
        adds=ProposeAdds(items=(ItemInput(description='leche'),))), now=NOW)
    assert decision.state.snapshot.proposal.reviewed_revision is None
    assert decision.state.snapshot.proposal.reviewed_update_id is None


def test_future_candidate_event_cannot_be_selected_as_history():
    state = reduce_guided(state_fixture(), message(2, 'uno'), candidate(2, (1, 1)), now=NOW).state
    future = state.question.candidate.model_copy(update={'source_update_id': 100})
    state = state.model_copy(update={'question': state.question.model_copy(update={'candidate': future})})
    decision = select(state, 'carne')
    assert decision.state == state
    assert decision.mutations == ()


def test_question_earlier_than_draft_expiry_still_rejects_expired_choice():
    state = start()
    state = state.model_copy(update={'question': state.question.model_copy(update={
        'expires_at': NOW + timedelta(minutes=1)})})
    choice = resolve_text_choice(message(3, 'Uno de cada'), state.question)
    decision = reduce_guided(state, message(3, 'Uno de cada'), choice, now=NOW + timedelta(minutes=2))
    assert decision.state == state
    assert decision.reason == 'expired'
