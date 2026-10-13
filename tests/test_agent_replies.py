"""Replies expose complete application facts, never invented persistence."""

from domain import Reply
from shopping_agent.contracts import (
    CompleteProposal,
    ItemInput,
    ItemPatch,
    ProposeAdds,
    ProposeChange,
    ToolResult,
)
from shopping_agent.proposals import answer_proposal, complete_proposal, prepare_proposal
from shopping_agent.replies import render_proposal, render_tool_results
from tests.agent_support import NOW, line, message, snapshot


def test_reply_covers_every_item_candidate_and_operand():
    rows = (line("a", quantity=1), line("b", quantity=4))
    decision = prepare_proposal(message(), ProposeAdds(items=(
        ItemInput(description="arroz", quantity=2),
        ItemInput(description="carne marca X 500g"))), snapshot(lines=rows), now=NOW)
    text = render_proposal(decision, snapshot(lines=rows)).text
    assert "Necesito arroz y carne" in text
    assert "carne marca X 500g" in text
    assert "a" in text and "b" in text and "1 envases" in text and "4 envases" in text
    assert "cantidad" in text and "separada" in text and "total" in text
    assert "sin guardar" in text and "guardado" not in text


def test_internal_only_duplicates_offer_only_separate_line_decisions():
    pending = prepare_proposal(message(), ProposeAdds(items=(
        ItemInput(description="arroz", quantity=2),
        ItemInput(description="arroz", quantity=3))), snapshot(), now=NOW)

    text = render_proposal(pending, snapshot()).text

    assert "posición 1" in text and "posición 2" in text
    assert "línea separada" in text
    assert "cantidad total" not in text


def test_review_ends_with_explicit_pending_confirmation_and_no_success():
    decision = prepare_proposal(message(), ProposeAdds(items=(
        ItemInput(description="arroz", quantity=2), ItemInput(description="carne", quantity=3))),
        snapshot(), now=NOW)
    text = render_proposal(decision, snapshot()).text
    assert "2 envases" in text and "3 envases" in text
    assert text.endswith("Pendiente, sin guardar. ¿Confirmas?")
    confirmed = answer_proposal(message("sí", 11), snapshot(decision.proposal), now=NOW)
    # Reducer authorization is NOT proof of a database commit.
    assert "guardado" not in render_proposal(confirmed, snapshot()).text


def test_oversized_review_cannot_grant_permission():
    items = tuple(ItemInput(description=f"producto {i} " + "x" * 145, quantity=2) for i in range(20))
    decision = prepare_proposal(message("petición " + "y" * 500), ProposeAdds(items=items),
                                snapshot(), now=NOW)
    assert decision.reason == "invalid"
    assert decision.proposal.reviewed_revision is None
    text = render_proposal(decision, snapshot()).text
    assert len(text) <= 4000 and "dividir" in text
    assert answer_proposal(message("sí", 12), snapshot(decision.proposal), now=NOW).mutations == ()


def test_tool_results_only_render_application_replies_in_order():
    results = (
        ToolResult(name="consultar_lista", data={"model_text": "Todo guardado"},
                   reply=Reply(text="Lista guardada: arroz, 1 envase."), terminal=False),
        ToolResult(name="proponer_altas", data={"confirmed": True},
                   reply=Reply(text="Carne pendiente, sin guardar."), terminal=True),
    )
    reply = render_tool_results(results)
    assert reply.text == "Lista guardada: arroz, 1 envase.\n\nCarne pendiente, sin guardar."
    assert "Todo guardado" not in reply.text


def test_oversized_tools_fail_honestly_instead_of_truncating():
    result = ToolResult(name="consultar_lista", data={}, reply=Reply(text="x" * 4001), terminal=False)
    reply = render_tool_results((result,))
    assert len(reply.text) <= 4000 and "dividir" in reply.text
    assert render_tool_results(()).text


def test_resolved_replacement_duplicate_is_explicitly_separate():
    rows = (line(), line("b", "carne", 4))
    pending = prepare_proposal(message(), ProposeChange(kind="replace", query="arroz",
        replacement="carne", quantity=2), snapshot(lines=rows), now=NOW)
    ready = complete_proposal(message("otra línea", 11),
        CompleteProposal(patches=(ItemPatch(position=1, duplicate_decision="separate"),)),
        snapshot(pending.proposal, rows), now=NOW)
    text = render_proposal(ready, snapshot(lines=rows)).text
    assert "línea separada" in text and "decide" not in text
    assert text.endswith("Pendiente, sin guardar. ¿Confirmas?")


def test_selected_origin_with_unknown_quantity_is_visible_in_total_review():
    rows = (line(quantity=None),)
    ready = prepare_proposal(message(), ProposeChange(kind="set_quantity", query="arroz", quantity=3),
                            snapshot(lines=rows), now=NOW)
    text = render_proposal(ready, snapshot(lines=rows)).text
    assert "cantidad desconocida" in text and "3 envases" in text


def test_oversized_tool_results_do_not_claim_a_real_commit_is_pending():
    result = ToolResult(name="resultado_guardado", data={},
                        reply=Reply(text="Guardado. " + "x" * 4000), terminal=True)
    text = render_tool_results((result,)).text
    assert "Pendiente" not in text and "sin guardar" not in text


def test_pending_increment_shows_supplied_delta_before_selection():
    rows = (line(quantity=1), line("b", quantity=4))
    pending = prepare_proposal(message(), ProposeChange(kind="increment", query="arroz", quantity=2),
                               snapshot(lines=rows), now=NOW)
    text = render_proposal(pending, snapshot(lines=rows)).text
    assert "Adicional solicitado: 2 envases" in text
    assert "1 envases" in text and "4 envases" in text and "Selecciona" in text


def test_replacement_destination_conflicts_are_not_offered_as_origin_indices():
    rows = (line("a", "arroz blanco"), line("b", "arroz integral"), line("c", "carne"))
    pending = prepare_proposal(message(), ProposeChange(kind="replace", query="arroz",
        replacement="carne", quantity=2), snapshot(lines=rows), now=NOW)
    text = render_proposal(pending, snapshot(lines=rows)).text
    assert "1: arroz blanco" in text and "2: arroz integral" in text
    assert "Conflictos de destino" in text and "carne [c" in text
    assert "3: carne" not in text
