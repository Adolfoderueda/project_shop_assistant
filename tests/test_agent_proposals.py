"""Authorization, ambiguity and arithmetic regressions for the pure reducer."""

from datetime import timedelta

import pytest

from dialogue import MAX_QUANTITY, LineRef
from shopping_agent.contracts import (
    AgentProposal,
    CompleteProposal,
    ItemInput,
    ItemPatch,
    ProposeAdds,
    ProposeChange,
    Reservation,
)
from shopping_agent.proposals import (
    answer_proposal,
    complete_proposal,
    parse_control,
    prepare_proposal,
)
from shopping_agent.replies import render_proposal
from tests.agent_support import NOW, line, message, snapshot


def adds(*items, lines=(), condition=None):
    return prepare_proposal(message(), ProposeAdds(items=items, condition=condition),
                            snapshot(lines=lines), now=NOW)


def edit(decision, *patches, lines=(), remove_condition=False):
    return complete_proposal(message("datos", 11),
        CompleteProposal(patches=patches, remove_condition=remove_condition),
        snapshot(decision.proposal, lines), now=NOW + timedelta(seconds=1))


def confirm(decision, lines=(), text="sí", **kwargs):
    return answer_proposal(message(text, 12), snapshot(decision.proposal, lines, **kwargs),
                           now=NOW + timedelta(seconds=2))


def test_multi_add_waits_for_all_quantities_and_review():
    first = adds(ItemInput(description="arroz"), ItemInput(description="carne"))
    assert len(first.proposal.items) == 2
    assert first.mutations == () and first.reason == "pending"
    assert confirm(first).mutations == ()
    partial = edit(first, ItemPatch(position=1, quantity=2))
    assert partial.reason == "pending" and partial.mutations == ()
    ready = edit(partial, ItemPatch(position=2, quantity=3))
    assert ready.reason == "reviewed" and ready.mutations == ()
    assert ready.proposal.reviewed_revision == ready.proposal.revision
    result = confirm(ready)
    assert result.reason == "confirmed"
    assert [(m.kind, m.description, m.quantity) for m in result.mutations] == [
        ("add", "arroz", 2), ("add", "carne", 3)]


def test_duplicate_and_increment_require_selection():
    rows = (line(), line("b", quantity=4))
    duplicate = adds(ItemInput(description="arroz", quantity=2), lines=rows)
    assert len(duplicate.proposal.items[0].candidates) == 2
    assert confirm(duplicate, rows).mutations == ()
    chosen = edit(duplicate, ItemPatch(position=1, candidate_index=2,
                  duplicate_decision="set_total"), lines=rows)
    assert confirm(chosen, rows).mutations[0].target.id == "b"
    increment = prepare_proposal(message("dos más de arroz"),
        ProposeChange(kind="increment", query="arroz", quantity=2), snapshot(lines=rows), now=NOW)
    assert increment.reason == "pending"
    assert increment.proposal.items[0].target is None
    chosen = edit(increment, ItemPatch(position=1, candidate_index=1), lines=rows)
    assert "1 + 2 = 3" in render_proposal(chosen, snapshot(lines=rows)).text
    mutation = confirm(chosen, rows).mutations[0]
    assert (mutation.expected_base, mutation.additional_quantity, mutation.quantity) == (1, 2, 3)


def test_unknown_base_is_not_zero():
    rows = (line(quantity=None),)
    pending = prepare_proposal(message(), ProposeChange(kind="increment", query="arroz", quantity=2),
                               snapshot(lines=rows), now=NOW)
    assert pending.reason == "pending" and confirm(pending, rows).mutations == ()
    assert "desconocida" in render_proposal(pending, snapshot(lines=rows)).text
    total = edit(pending, ItemPatch(position=1, duplicate_decision="set_total", quantity=5), lines=rows)
    assert confirm(total, rows).mutations[0].kind == "set_quantity"
    assert confirm(total, rows).mutations[0].quantity == 5


def test_missing_increment_offers_new_add_without_more_in_name():
    pending = prepare_proposal(message("dos más de arroz"),
        ProposeChange(kind="increment", query="arroz", quantity=2), snapshot(), now=NOW)
    assert pending.reason == "pending"
    assert "alta nueva" in render_proposal(pending, snapshot()).text
    ready = edit(pending, ItemPatch(position=1, duplicate_decision="separate"))
    assert confirm(ready).mutations[0].description == "arroz"


def test_diaper_unit_and_overflow():
    pending = adds(ItemInput(description="pañales Dodot talla 4", quantity=2))
    assert pending.reason == "diaper_unit" and confirm(pending).mutations == ()
    invalid = edit(pending, ItemPatch(position=1, unit="botes"))
    assert invalid.reason == "diaper_unit"
    ready = edit(pending, ItemPatch(position=1, unit="paquetes"))
    assert confirm(ready).mutations[0].unit == "paquetes"
    rows = (line(quantity=MAX_QUANTITY),)
    overflow = prepare_proposal(message(), ProposeChange(kind="increment", query="arroz", quantity=1),
                                snapshot(lines=rows), now=NOW)
    assert overflow.reason == "quantity_range" and confirm(overflow, rows).mutations == ()


def test_cancel_only_discards_proposal():
    rows = (line(),)
    pending = adds(ItemInput(description="carne", quantity=2), lines=rows)
    result = confirm(pending, rows, text="cancelar")
    assert result.reason == "cancelled" and result.proposal is None and result.mutations == ()
    assert rows[0].quantity == 1
    assert confirm(pending, rows, text="no").reason == "rejected"


def test_condition_blocks_confirmation():
    pending = adds(ItemInput(description="carne", quantity=2), condition="si está en oferta")
    assert pending.reason == "condition"
    assert pending.proposal.reviewed_revision is None
    assert confirm(pending).mutations == ()
    ready = edit(pending, remove_condition=True)
    assert ready.reason == "reviewed" and ready.proposal.revision == 2
    assert ready.mutations == () and len(confirm(ready).mutations) == 1


def test_same_target_twice_and_internal_duplicates_block_review():
    rows = (line(),)
    duplicate = adds(ItemInput(description="Arroz", quantity=2),
                     ItemInput(description="arroz", quantity=3))
    assert duplicate.reason == "pending" and confirm(duplicate).mutations == ()
    separate = edit(duplicate, ItemPatch(position=1, duplicate_decision="separate"),
                    ItemPatch(position=2, duplicate_decision="separate"))
    assert len(confirm(separate).mutations) == 2
    saved = adds(ItemInput(description="arroz", quantity=2),
                 ItemInput(description="arroz", quantity=3), lines=rows)
    conflict = edit(saved, ItemPatch(position=1, candidate_index=1, duplicate_decision="set_total"),
                    ItemPatch(position=2, candidate_index=1, duplicate_decision="set_total"), lines=rows)
    assert conflict.reason == "invalid" and confirm(conflict, rows).mutations == ()


def test_mixed_yes_edit_cannot_commit():
    ready = adds(ItemInput(description="carne", quantity=2))
    for text in ("sí y añade arroz", "sí, pero tres", "confirmar carne", "sí!", "si no"):
        assert parse_control(text, ready.proposal, now=NOW) is None
        assert confirm(ready, text=text).mutations == ()
    edited = edit(ready, ItemPatch(position=1, quantity=3))
    assert edited.proposal.revision == 2
    assert edited.proposal.reviewed_update_id == 11
    assert answer_proposal(message("sí", 11), snapshot(edited.proposal), now=NOW).mutations == ()


def test_social_read_does_not_renew_ttl():
    ready = adds(ItemInput(description="carne", quantity=2))
    for text in ("hola", "qué lista tengo"):
        result = answer_proposal(message(text, 12), snapshot(ready.proposal),
                                 now=NOW + timedelta(minutes=10))
        assert result.proposal == ready.proposal and result.mutations == ()
        after_expiry = answer_proposal(message(text, 12), snapshot(ready.proposal),
                                      now=NOW + timedelta(minutes=16))
        assert after_expiry.proposal == ready.proposal and after_expiry.mutations == ()
    expired = answer_proposal(message("sí", 12), snapshot(ready.proposal),
                              now=NOW + timedelta(minutes=15))
    assert expired.reason == "expired" and expired.mutations == ()


@pytest.mark.parametrize("text", ["sí", "confirmo", "confirmar", "no", "2", "cancelar"])
def test_out_of_context_controls_grant_no_permission(text):
    assert parse_control(text, None, now=NOW) is None
    assert answer_proposal(message(text), snapshot(), now=NOW).mutations == ()


@pytest.mark.parametrize("change", ["revision", "missing", "reserved", "duplicate", "owner"])
def test_confirmation_revalidates_entire_snapshot(change):
    rows = (line(),)
    ready = prepare_proposal(message(), ProposeChange(kind="increment", query="arroz", quantity=2),
                            snapshot(lines=rows), now=NOW)
    current = rows
    reservations = ()
    snap = snapshot(ready.proposal, rows)
    if change == "revision":
        current = (line(revision=2),)
    if change == "missing":
        current = ()
    if change == "reserved":
        reservations = (Reservation(line_id="a", order_id="o"),)
    if change == "duplicate":
        current = (*rows, line("b"))
    if change == "owner":
        snap = snap.model_copy(update={"user_id": 3})
    else:
        snap = snapshot(ready.proposal, current, reservations)
    assert answer_proposal(message("sí", 12), snap, now=NOW).mutations == ()


def test_variants_preserved_and_multiple_matches_never_choose_first():
    rows = (line("a", "leche entera marca A 500g"), line("b", "leche avena marca B 700g"))
    pending = prepare_proposal(message(), ProposeChange(kind="set_quantity", query="leche", quantity=2),
                               snapshot(lines=rows), now=NOW)
    assert len(pending.proposal.items[0].candidates) == 2
    assert pending.proposal.items[0].target is None
    ready = edit(pending, ItemPatch(position=1, candidate_index=2), lines=rows)
    assert "leche avena marca B 700g" in render_proposal(ready, snapshot(lines=rows)).text
    assert confirm(ready, rows).mutations[0].target.id == "b"


def test_selection_bounds_and_ambiguous_quantity_do_not_edit():
    pending = adds(ItemInput(description="arroz"), ItemInput(description="carne"))
    assert parse_control("2", pending.proposal, now=NOW) is None
    invalid = edit(pending, ItemPatch(position=3, quantity=2))
    assert invalid.reason == "invalid" and invalid.proposal == pending.proposal
    rows = (line(), line("b"))
    pending = adds(ItemInput(description="arroz", quantity=2), lines=rows)
    assert edit(pending, ItemPatch(position=1, candidate_index=3), lines=rows).reason == "invalid"


def test_closed_answers_complete_single_question_without_writes():
    pending = adds(ItemInput(description="carne"))
    answer = parse_control("3 envases", pending.proposal, now=NOW)
    assert (answer.kind, answer.quantity, answer.unit) == ("quantity", 3, "envases")
    ready = answer_proposal(message("3 envases", 11), snapshot(pending.proposal), now=NOW)
    assert ready.reason == "reviewed" and ready.mutations == ()


def test_closed_diaper_quantity_supplies_required_unit():
    pending = adds(ItemInput(description="pañales", quantity=2))
    ready = answer_proposal(message("2 paquetes", 11), snapshot(pending.proposal), now=NOW)
    assert ready.reason == "reviewed" and ready.proposal.items[0].unit == "paquetes"


@pytest.mark.parametrize("kind", ["set_quantity", "increment"])
@pytest.mark.parametrize("multiple", [False, True])
def test_qualifier_only_diaper_query_accepts_closed_pack_quantity(kind, multiple):
    rows = (line("a", "pañales talla 4", 2),)
    if multiple:
        rows = (*rows, line("b", "pañales Dodot talla 4", 3))
    pending = prepare_proposal(message("dos de talla 4"),
        ProposeChange(kind=kind, query="talla 4", quantity=2), snapshot(lines=rows), now=NOW)
    if multiple:
        pending = answer_proposal(message("1", 11), snapshot(pending.proposal, rows), now=NOW)
    assert pending.reason == "diaper_unit"
    assert pending.proposal.items[0].unit is None
    # The selected-product requirement must survive the shared serialization boundary.
    restored = AgentProposal.model_validate_json(pending.proposal.model_dump_json())
    parsed = parse_control("2 paquetes", restored, now=NOW)
    assert parsed is not None and (parsed.kind, parsed.quantity, parsed.unit) == ("quantity", 2, "paquetes")
    ready = answer_proposal(message("2 paquetes", 12), snapshot(restored, rows), now=NOW)
    assert ready.reason == "reviewed" and ready.mutations == ()
    assert ready.proposal.items[0].unit == "paquetes"
    confirmed = answer_proposal(message("sí", 13), snapshot(ready.proposal, rows), now=NOW)
    assert len(confirmed.mutations) == 1 and confirmed.mutations[0].unit == "paquetes"
    assert confirmed.mutations[0].quantity == (4 if kind == "increment" else 2)


def test_duplicate_closed_total_choice_then_selection():
    rows = (line(), line("b", quantity=4))
    pending = adds(ItemInput(description="arroz", quantity=2), lines=rows)
    chosen = answer_proposal(message("cambiar cantidad", 11), snapshot(pending.proposal, rows), now=NOW)
    assert chosen.proposal.items[0].duplicate_decision == "set_total"
    assert chosen.reason == "pending" and chosen.mutations == ()
    selected = answer_proposal(message("2", 12), snapshot(chosen.proposal, rows), now=NOW)
    assert selected.reason == "reviewed" and selected.proposal.items[0].target.id == "b"


def test_replacement_keeps_origin_and_checks_destination_conflicts():
    rows = (line("a", "arroz"), line("b", "carne", 4))
    pending = prepare_proposal(message(),
        ProposeChange(kind="replace", query="arroz", replacement="carne", quantity=2),
        snapshot(lines=rows), now=NOW)
    assert pending.reason == "pending"
    ready = edit(pending, ItemPatch(position=1, duplicate_decision="separate"), lines=rows)
    mutation = confirm(ready, rows).mutations[0]
    assert (mutation.kind, mutation.target.id, mutation.description, mutation.quantity) == (
        "replace", "a", "carne", 2)


def test_replacement_without_destination_duplicates_needs_only_full_review():
    rows = (line(),)
    ready = prepare_proposal(message(),
        ProposeChange(kind="replace", query="arroz", replacement="carne", quantity=3),
        snapshot(lines=rows), now=NOW)
    assert ready.reason == "reviewed" and ready.mutations == ()
    assert confirm(ready, rows).mutations[0].description == "carne"


def test_injected_target_outside_offered_candidates_cannot_commit():
    rows = (line(), line("b", "carne"))
    pending = adds(ItemInput(description="arroz", quantity=2), lines=rows)
    ready = edit(pending, ItemPatch(position=1, candidate_index=1,
                 duplicate_decision="set_total"), lines=rows)
    item = ready.proposal.items[0].model_copy(update={"target": LineRef(id="b", revision=1)})
    proposal = ready.proposal.model_copy(update={"items": (item,)})
    assert answer_proposal(message("sí", 12), snapshot(proposal, rows), now=NOW).mutations == ()


def test_edited_increment_requires_new_review_and_correct_arithmetic():
    rows = (line(quantity=4),)
    ready = prepare_proposal(message(), ProposeChange(kind="increment", query="arroz", quantity=2),
                            snapshot(lines=rows), now=NOW)
    changed = edit(ready, ItemPatch(position=1, quantity=3), lines=rows)
    assert changed.proposal.revision == 2 and changed.proposal.reviewed_revision == 2
    result = confirm(changed, rows)
    assert (result.mutations[0].expected_base, result.mutations[0].additional_quantity,
            result.mutations[0].quantity) == (4, 3, 7)


def test_duplicate_added_after_review_blocks_entire_addition_batch():
    ready = adds(ItemInput(description="arroz", quantity=2), ItemInput(description="carne", quantity=3))
    assert confirm(ready, (line(),)).reason == "stale"
    assert confirm(ready, (line(),)).mutations == ()
