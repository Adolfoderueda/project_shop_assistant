from domain import Reply
from shopping_agent.contracts import ProposalItem
from shopping_agent.guided_controller import reduce_guided
from shopping_agent.guided_replies import render_question, render_review, review_fits
from tests.guided_helpers import NOW, candidate, increment_state, message, state_fixture, with_items


def test_question_is_text_with_logical_options_not_tokens():
    state = reduce_guided(state_fixture(), message(2, 'x'), None, now=NOW).state
    reply = render_question(state.question)
    assert reply.keyboard is None
    assert 'huevos' in reply.text and 'carne' in reply.text and 'atun' in reply.text
    assert 'Uno de cada' in reply.text


def test_review_is_full_and_not_a_save_claim():
    reply = render_review(state_fixture(quantities=(1, 2, 3)))
    assert '1 envases' in reply.text and '2 envases' in reply.text and '3 envases' in reply.text
    assert 'sin guardar' in reply.text
    assert reply.keyboard is None


def test_astral_characters_use_utf16_limit():
    assert review_fits(Reply(text='😀' * 2000))
    assert not review_fits(Reply(text='😀' * 2001))
    assert not review_fits(Reply(text='x' * 4001))


def test_oversized_review_does_not_create_confirmable_question():
    state = state_fixture(quantities=(1, 1, 1))
    state = state.model_copy(update={'snapshot': state.snapshot.model_copy(update={
        'proposal': state.snapshot.proposal.model_copy(update={'original_text': '😀' * 2001})})})
    decision = reduce_guided(state, message(2, 'revisar'), None, now=NOW)
    assert decision.state.question is None
    assert decision.state.review is None
    assert decision.reason == 'too_long'
    assert 'dividir' in decision.reply.text
    assert not review_fits(render_review(state))


def test_twenty_item_review_is_full():
    state = with_items(tuple(ProposalItem(position=i, kind='add', description=f'producto {i}', quantity=i)
                             for i in range(1, 21)))
    reply = render_review(state)
    assert '1. alta nueva: producto 1: 1 envases.' in reply.text
    assert '20. alta nueva: producto 20: 20 envases.' in reply.text
    assert review_fits(reply)
    assert reduce_guided(state, message(2, 'x'), None, now=NOW).state.question.kind == 'review'


def test_increment_summary_shows_base_delta_and_total():
    reply = render_review(increment_state())
    assert 'Base + adicional = total: 2 + 3 = 5 envases.' in reply.text


def test_review_question_renders_the_exact_witness_summary():
    state = reduce_guided(state_fixture(quantities=(1, 2, 3)), message(2, 'x'), None, now=NOW).state
    assert render_question(state.question) == render_review(state)


def test_candidate_amount_is_visible_as_unapplied_data():
    state = reduce_guided(state_fixture(), message(2, 'dos'), candidate(2, (1, 2)), now=NOW).state
    reply = render_question(state.question)
    assert '2' in reply.text
    assert 'candidata' in reply.text and 'sin aplicar' in reply.text
    assert state.snapshot.proposal.items[0].quantity is None
