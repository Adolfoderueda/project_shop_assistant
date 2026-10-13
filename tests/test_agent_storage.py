import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from domain import IncomingMessage, Reply
from storage import Repository

NOW = datetime(2026, 10, 8, tzinfo=UTC)


@pytest.fixture
def repo(tmp_path):
    result = Repository(tmp_path / 'agent.db')
    result.migrate()
    return result


def ingest(repo, update, text, user=7):
    repo.ingest_batch([IncomingMessage(update_id=update, user_id=user, chat_id=user, text=text)], update + 1)


def propose(repo, update=1, quantity=2):
    ingest(repo, update, 'arroz y carne')
    return repo.apply_agent_operation(update, 'proponer_altas', {'items': [
        {'description': 'arroz', 'quantity': quantity}, {'description': 'carne', 'quantity': 3}
    ]}, None, now=NOW)


def test_propose_and_complete_never_insert_list_lines(repo):
    propose(repo, quantity=None)
    ingest(repo, 2, 'dos de arroz')
    result = repo.apply_agent_operation(2, 'completar_propuesta',
        {'patches': [{'position': 1, 'quantity': 2}]}, 1, now=NOW)
    assert result.terminal and not repo.list_lines()
    snapshot = repo.agent_snapshot(2, now=NOW)
    assert snapshot.proposal.reviewed_update_id == 2
    assert repo.message_result(2)[1] == result.reply


def test_confirm_commits_full_batch_and_one_notice(repo):
    propose(repo)
    ingest(repo, 2, 'sí')
    reply = repo.apply_agent_control(2, now=NOW)
    assert 'guardad' in reply.text.lower()
    assert [(l.description, l.quantity) for l in repo.list_lines()] == [('arroz', 2), ('carne', 3)]
    assert repo.agent_snapshot(2, now=NOW).proposal is None
    assert repo.message_result(2)[1] == reply
    assert len(repo.pending_notices()) == 2


def test_replay_and_second_yes_do_not_repeat(repo):
    propose(repo)
    ingest(repo, 2, 'sí')
    first = repo.apply_agent_control(2, now=NOW)
    assert repo.apply_agent_control(2, now=NOW) == first
    ingest(repo, 3, 'sí')
    assert 'No hay' in repo.apply_agent_control(3, now=NOW).text
    assert len(repo.list_lines()) == 2
    assert len(repo.pending_notices()) == 3


def test_failure_on_second_write_rolls_back_everything(repo):
    propose(repo)
    ingest(repo, 2, 'sí')
    with repo._connection(write=True) as db:
        db.executescript("CREATE TRIGGER fail_second BEFORE INSERT ON list_lines WHEN NEW.description='carne' BEGIN SELECT RAISE(ABORT,'failure'); END;")
    with pytest.raises(sqlite3.IntegrityError):
        repo.apply_agent_control(2, now=NOW)
    assert not repo.list_lines()
    assert repo.message_result(2)[1] is None
    assert repo.agent_snapshot(2, now=NOW).proposal.reviewed_update_id == 1


def test_target_revision_reservation_and_new_duplicate_invalidate(repo):
    propose(repo)
    ingest(repo, 2, '/anadir 1 arroz')
    from domain import Intent, IntentLine
    repo.apply_intent(2, Intent(action='add', lines=[IntentLine(description='arroz', quantity=1)]), 'dry_run')
    ingest(repo, 3, 'sí')
    assert 'cambiado' in repo.apply_agent_control(3, now=NOW).text
    assert len(repo.list_lines()) == 1
    assert repo.agent_snapshot(3, now=NOW).proposal is None


def test_forged_confirmation_or_foreign_owner_is_rejected(repo):
    ingest(repo, 1, 'arroz')
    with pytest.raises(ValueError):
        repo.apply_agent_operation(1, 'proponer_altas', {'items': [{'description': 'arroz', 'quantity': 2}], 'confirm': True}, None, now=NOW)
    propose(repo, update=2)
    ingest(repo, 3, 'sí', user=8)
    assert 'No hay' in repo.apply_agent_control(3, now=NOW).text
    assert not repo.list_lines()
    with pytest.raises(PermissionError):
        repo.assert_authorized_owner(7)


@pytest.mark.parametrize('field,value', [('original_text', 'forged'), ('reviewed_update_id', 999), ('user_id', 8)])
def test_persisted_corruption_cannot_grant_permission(repo, field, value):
    propose(repo)
    with repo._connection(write=True) as db:
        payload = json.loads(db.execute('SELECT proposal_json FROM agent_proposals').fetchone()[0])
        payload[field] = value
        db.execute('UPDATE agent_proposals SET proposal_json=?', (json.dumps(payload),))
    ingest(repo, 2, 'sí')
    repo.apply_agent_control(2, now=NOW)
    assert not repo.list_lines()


def test_route_toggle_revokes_old_yes(repo):
    assert repo.set_conversation_route(7, 7, 'agent', now=NOW)
    propose(repo)
    assert not repo.set_conversation_route(7, 7, 'agent', now=NOW)
    assert repo.set_conversation_route(7, 7, 'legacy', now=NOW)
    assert repo.set_conversation_route(7, 7, 'agent', now=NOW)
    ingest(repo, 2, 'sí')
    assert 'No hay' in repo.apply_agent_control(2, now=NOW).text
    assert not repo.list_lines()


def test_social_and_completion_reply_do_not_renew_proposal(repo):
    propose(repo)
    before = repo.agent_snapshot(1, now=NOW).proposal
    ingest(repo, 2, 'hola')
    assert repo.apply_agent_control(2, now=NOW + timedelta(minutes=1)) is None
    repo.complete_agent_reply(2, Reply(text='Hola'))
    assert repo.agent_snapshot(2, now=NOW).proposal == before


@pytest.mark.parametrize('damage', ['quantity', 'duplicate', 'notice', 'review_text'])
def test_review_witness_cannot_be_reused_for_modified_proposal(repo, damage):
    propose(repo)
    with repo._connection(write=True) as db:
        if damage in {'quantity', 'duplicate'}:
            payload = json.loads(db.execute('SELECT proposal_json FROM agent_proposals').fetchone()[0])
            payload['items'][0]['quantity' if damage == 'quantity' else 'duplicate_decision'] = 9 if damage == 'quantity' else 'separate'
            db.execute('UPDATE agent_proposals SET proposal_json=?', (json.dumps(payload),))
        elif damage == 'notice':
            db.execute('DELETE FROM outbox WHERE update_id=1')
        else:
            db.execute('UPDATE inbox SET reply_json=? WHERE update_id=1', (Reply(text='forged').model_dump_json(),))
    ingest(repo, 2, 'sí')
    repo.apply_agent_control(2, now=NOW)
    assert not repo.list_lines()


@pytest.mark.parametrize('arguments', [
    {'items': ({'description': 'arroz', 'quantity': 2},)},
    {'items': [{'description': 'arroz', 'quantity': True}]},
    {'items': [{'description': 'arroz', 'quantity': '2'}]},
])
def test_only_raw_strict_json_arguments_are_accepted(repo, arguments):
    ingest(repo, 1, 'arroz')
    with pytest.raises(ValueError):
        repo.apply_agent_operation(1, 'proponer_altas', arguments, None, now=NOW)
    assert repo.message_result(1)[1] is None


@pytest.mark.parametrize('damage', ['revision', 'reservation'])
def test_target_change_or_reservation_prevents_all_mutations(repo, damage):
    from tests.dialogue_support import seed_line
    line = seed_line(repo, 'arroz', 2)
    ingest(repo, 2, 'más arroz')
    repo.apply_agent_operation(2, 'proponer_cambio', {'kind': 'increment', 'query': 'arroz', 'quantity': 3}, None, now=NOW)
    with repo._connection(write=True) as db:
        if damage == 'revision':
            db.execute('UPDATE list_lines SET quantity=8,revision=revision+1 WHERE id=?', (line.id,))
        else:
            db.execute("INSERT INTO orders VALUES ('reservation','dry_run',1,'2026-10-08')")
            db.execute("INSERT INTO reservations VALUES (?,'reservation')", (line.id,))
    before = repo.list_lines()
    ingest(repo, 3, 'sí')
    repo.apply_agent_control(3, now=NOW)
    assert repo.list_lines() == before
    assert repo.agent_snapshot(3, now=NOW).proposal is None


def test_selected_diaper_unit_is_rederived_not_trusted(repo):
    from tests.dialogue_support import seed_line
    seed_line(repo, 'Dodot talla 3 pañales', 2)
    ingest(repo, 2, 'más talla 3')
    result = repo.apply_agent_operation(2, 'proponer_cambio', {'kind': 'increment', 'query': 'talla 3', 'quantity': 3}, None, now=NOW)
    assert 'explícitamente' in result.reply.text
    with repo._connection(write=True) as db:
        payload = json.loads(db.execute('SELECT proposal_json FROM agent_proposals').fetchone()[0])
        payload['items'][0]['requires_explicit_unit'] = False
        db.execute('UPDATE agent_proposals SET proposal_json=?', (json.dumps(payload),))
    ingest(repo, 3, 'sí')
    repo.apply_agent_control(3, now=NOW)
    assert repo.list_lines()[0].quantity == 2


def test_command_origin_uses_caller_transaction_and_revokes_agent(repo):
    propose(repo)
    ingest(repo, 2, '/anadir arroz')
    with pytest.raises(RuntimeError), repo._connection(write=True) as db:
        source = db.execute('SELECT * FROM inbox WHERE update_id=2').fetchone()
        *_, reply = repo._apply_dialogue(db, source, None, 'dry_run', now=NOW)
        repo._record_command_origin(db, db.execute('SELECT * FROM inbox WHERE update_id=2').fetchone())
        repo._complete_reply(db, source, reply)
        raise RuntimeError('rollback')
    assert repo.command_origin(7, 7) is None
    assert repo.agent_snapshot(2, now=NOW).proposal is not None
    with repo._connection(write=True) as db:
        source = db.execute('SELECT * FROM inbox WHERE update_id=2').fetchone()
        *_, reply = repo._apply_dialogue(db, source, None, 'dry_run', now=NOW)
        repo._record_command_origin(db, source)
        repo._complete_reply(db, source, reply)
    assert repo.command_origin(7, 7).update_id == 2
    assert repo.agent_snapshot(2, now=NOW).proposal is None
    ingest(repo, 3, '/unknown')
    with repo._connection(write=True) as db, pytest.raises(ValueError):
        repo._record_command_origin(db, db.execute('SELECT * FROM inbox WHERE update_id=3').fetchone())


@pytest.mark.parametrize('text,retained', [('/anadir arroz', True), ('necesito arroz', False)])
def test_initial_agent_route_preserves_only_inbox_backed_command_context(repo, text, retained):
    from domain import Intent, IntentLine
    ingest(repo, 1, text)
    repo.apply_dialogue(1, Intent(action='add', lines=[IntentLine(description='arroz')]), 'dry_run', now=NOW)
    assert repo.set_conversation_route(7, 7, 'agent', now=NOW)
    assert (repo.dialogue_state(7, 7, now=NOW) is not None) == retained
    assert (repo.command_origin(7, 7) is not None) == retained


@pytest.mark.parametrize('damage', ['read_only', 'incomplete', 'description', 'witness'])
def test_command_provenance_rejects_unrelated_or_uncommitted_permission(repo, damage):
    ingest(repo, 1, '/anadir arroz')
    if damage == 'incomplete':
        with repo._connection(write=True) as db:
            source = db.execute('SELECT * FROM inbox WHERE update_id=1').fetchone()
            repo._apply_dialogue(db, source, None, 'dry_run', now=NOW)
    else:
        repo.apply_dialogue(1, None, 'dry_run', now=NOW)
        with repo._connection(write=True) as db:
            if damage == 'read_only':
                db.execute("UPDATE inbox SET text='/lista' WHERE update_id=1")
            elif damage == 'description':
                state = repo._read_dialogue_state(db, 7, 7)
                state = state.model_copy(update={'focus': state.focus.model_copy(update={'description': 'carne'})})
                repo._write_dialogue_state(db, state, 7, 7)
            else:
                payload = Reply(text='unrelated reply').model_dump_json()
                db.execute('UPDATE inbox SET reply_json=? WHERE update_id=1', (payload,))
                db.execute('UPDATE outbox SET reply_json=? WHERE update_id=1', (payload,))
    assert repo.command_origin(7, 7) is None
    assert repo.set_conversation_route(7, 7, 'agent', now=NOW)
    assert repo.dialogue_state(7, 7, now=NOW) is None


def test_record_origin_rejects_read_only_command_and_missing_state(repo):
    ingest(repo, 1, '/anadir arroz')
    with repo._connection(write=True) as db, pytest.raises(ValueError):
        repo._record_command_origin(db, db.execute('SELECT * FROM inbox WHERE update_id=1').fetchone())
    repo.apply_dialogue(1, None, 'dry_run', now=NOW)
    ingest(repo, 2, '/lista')
    with repo._connection(write=True) as db, pytest.raises(ValueError):
        source = db.execute('SELECT * FROM inbox WHERE update_id=2').fetchone()
        repo._apply_dialogue(db, source, None, 'dry_run', now=NOW)
        repo._record_command_origin(db, source)


def test_initial_route_preserves_real_remove_candidates(repo):
    from tests.dialogue_support import seed_line
    seed_line(repo, 'arroz blanco', 2)
    seed_line(repo, 'arroz integral', 3)
    ingest(repo, 3, '/quitar arroz')
    repo.apply_dialogue(3, None, 'dry_run', now=NOW)
    before = repo.dialogue_state(7, 7, now=NOW)
    assert before.question == 'remove_id'
    assert repo.set_conversation_route(7, 7, 'agent', now=NOW)
    assert repo.dialogue_state(7, 7, now=NOW) == before
    assert repo.command_origin(7, 7).update_id == 3


def test_purchase_quantity_origin_cannot_support_another_target(repo):
    from dialogue import LineRef
    from tests.dialogue_support import seed_line
    seed_line(repo, 'arroz')
    other = seed_line(repo, 'carne')
    ingest(repo, 3, '/comprar')
    repo.apply_dialogue(3, None, 'dry_run', now=NOW)
    assert repo.command_origin(7, 7).update_id == 3
    with repo._connection(write=True) as db:
        state = repo._read_dialogue_state(db, 7, 7)
        ref = LineRef(id=other.id, revision=other.revision)
        state = state.model_copy(update={'target': ref, 'focus': state.focus.model_copy(update={'line': ref, 'description': 'carne'})})
        repo._write_dialogue_state(db, state, 7, 7)
    assert repo.command_origin(7, 7) is None


def test_read_only_origin_cannot_accredit_increment_confirmation(repo):
    from dialogue import DIALOGUE_TTL, DialogueState, LineRef, ProductMention
    from tests.dialogue_support import seed_line
    line = seed_line(repo, 'arroz', 2)
    ingest(repo, 2, '/lista')
    repo.apply_dialogue(2, None, 'dry_run', now=NOW)
    ref = LineRef(id=line.id, revision=line.revision)
    state = DialogueState(user_id=7, chat_id=7, pending_kind='increment',
        focus=ProductMention(description='arroz', source_update_id=2, line=ref), target=ref,
        base_quantity=2, additional_quantity=3, proposal_quantity=5, question='confirm_increment',
        updated_at=NOW, expires_at=NOW + DIALOGUE_TTL)
    with repo._connection(write=True) as db:
        repo._write_dialogue_state(db, state, 7, 7)
    assert repo.command_origin(7, 7) is None
    repo.set_conversation_route(7, 7, 'agent', now=NOW)
    assert repo.dialogue_state(7, 7, now=NOW) is None
    assert repo.list_lines()[0].quantity == 2


def test_real_slash_duplicate_selection_preserves_quantity_continuation(repo):
    from tests.dialogue_support import seed_line
    line = seed_line(repo, 'arroz', 2)
    ingest(repo, 2, '/anadir arroz')
    repo.apply_dialogue(2, None, 'dry_run', now=NOW)
    ingest(repo, 3, 'cambiar cantidad')
    repo.apply_dialogue(3, None, 'dry_run', now=NOW + timedelta(seconds=1))
    before = repo.dialogue_state(7, 7, now=NOW)
    assert before.question == 'quantity' and before.target.id == line.id
    assert repo.command_origin(7, 7).update_id == 2
    repo.set_conversation_route(7, 7, 'agent', now=NOW)
    assert repo.dialogue_state(7, 7, now=NOW) == before


@pytest.mark.parametrize('choice', ['añadir otra línea', '2'])
@pytest.mark.parametrize('damage', [None, 'missing_choice', 'incomplete_choice', 'choice_reply', 'choice_text', 'choice_owner', 'candidates'])
def test_duplicate_add_quantity_requires_real_committed_choice_trace(repo, damage, choice):
    from tests.dialogue_support import seed_line
    line = seed_line(repo, 'arroz', 2)
    ingest(repo, 2, '/anadir arroz')
    repo.apply_dialogue(2, None, 'dry_run', now=NOW)
    ingest(repo, 3, choice)
    repo.apply_dialogue(3, None, 'dry_run', now=NOW + timedelta(seconds=1))
    state = repo.dialogue_state(7, 7, now=NOW)
    assert state.question == 'add_quantity' and state.duplicate_confirmed
    assert state.candidates[0].id == line.id
    with repo._connection(write=True) as db:
        if damage == 'missing_choice':
            db.execute('DELETE FROM outbox WHERE update_id=3')
        elif damage == 'incomplete_choice':
            db.execute('UPDATE inbox SET completed=0 WHERE update_id=3')
        elif damage == 'choice_reply':
            payload = Reply(text='unrelated choice reply').model_dump_json()
            db.execute('UPDATE inbox SET reply_json=? WHERE update_id=3', (payload,))
            db.execute('UPDATE outbox SET reply_json=? WHERE update_id=3', (payload,))
        elif damage == 'choice_text':
            db.execute("UPDATE inbox SET text='hola' WHERE update_id=3")
        elif damage == 'choice_owner':
            db.execute('UPDATE inbox SET user_id=8,chat_id=8 WHERE update_id=3')
        elif damage == 'candidates':
            from dialogue import LineRef
            damaged = state.model_copy(update={'candidates': (LineRef(id=line.id, revision=2),)})
            repo._write_dialogue_state(db, damaged, 7, 7)
    origin = repo.command_origin(7, 7)
    if damage is None:
        assert origin is not None and origin.update_id == 2
    else:
        assert origin is None
    assert repo.set_conversation_route(7, 7, 'agent', now=NOW)
    assert repo.dialogue_state(7, 7, now=NOW) == (state if damage is None else None)
    assert repo.list_lines() == [line]
    if damage is None:
        recovered = Repository(repo.path)
        assert recovered.command_origin(7, 7).update_id == 2
        ingest(recovered, 4, '3')
        recovered.apply_dialogue(4, None, 'dry_run', now=NOW + timedelta(seconds=2))
        saved = recovered.list_lines()
        assert saved[0] == line
        assert len(saved) == 2 and saved[1].description == 'arroz' and saved[1].quantity == 3


def test_expired_and_embedded_confirmation_never_commits(repo):
    propose(repo)
    ingest(repo, 2, 'sí, añade otro producto')
    assert repo.apply_agent_control(2, now=NOW) is None
    ingest(repo, 3, 'sí')
    assert 'caducado' in repo.apply_agent_control(3, now=NOW + timedelta(minutes=15)).text
    assert not repo.list_lines()


@pytest.mark.parametrize('kind,arguments,description,quantity', [
    ('increment', {'quantity': 3}, 'arroz', 5),
    ('set_quantity', {'quantity': 4}, 'arroz', 4),
    ('replace', {'quantity': 6, 'replacement': 'avena'}, 'avena', 6),
])
def test_confirmed_changes_update_exactly_one_revision(repo, kind, arguments, description, quantity):
    from tests.dialogue_support import seed_line
    line = seed_line(repo, 'arroz', 2)
    ingest(repo, 2, 'cambia arroz')
    repo.apply_agent_operation(2, 'proponer_cambio', {'kind': kind, 'query': 'arroz', **arguments}, None, now=NOW)
    assert repo.list_lines()[0] == line
    ingest(repo, 3, 'sí')
    repo.apply_agent_control(3, now=NOW)
    saved = repo.list_lines()[0]
    assert (saved.id, saved.revision, saved.description, saved.quantity) == (line.id, 2, description, quantity)


def test_unknown_operation_cannot_touch_inbox_or_list(repo):
    ingest(repo, 1, 'arroz')
    with pytest.raises(ValueError):
        repo.apply_agent_operation(1, 'confirmar', {}, None, now=NOW)
    assert repo.message_result(1)[1] is None
    assert not repo.list_lines()


def test_pending_proposal_requires_committed_original_inbox_notice(repo):
    propose(repo, quantity=None)
    with repo._connection(write=True) as db:
        db.execute('DELETE FROM outbox WHERE update_id=1')
    ingest(repo, 2, 'dos de arroz')
    repo.apply_agent_operation(2, 'completar_propuesta', {'patches': [{'position': 1, 'quantity': 2}]}, 1, now=NOW)
    ingest(repo, 3, 'sí')
    repo.apply_agent_control(3, now=NOW)
    assert not repo.list_lines()


@pytest.mark.parametrize('table', ['agent_proposals', 'conversation_routes'])
def test_owner_assertion_checks_new_table_keys(repo, table):
    propose(repo)
    repo.set_conversation_route(7, 7, 'agent', now=NOW)
    if table == 'agent_proposals':
        # Route synchronization deliberately revoked the first proposal.
        propose(repo, update=2)
    with repo._connection(write=True) as db:
        db.execute(f'UPDATE {table} SET user_id=8')
    with pytest.raises(PermissionError):
        repo.assert_authorized_owner(7)


def test_overlong_summary_cannot_acquire_review_permission(repo):
    ingest(repo, 1, 'x' * 3900)
    result = repo.apply_agent_operation(1, 'proponer_altas', {'items': [{'description': 'arroz', 'quantity': 2}]}, None, now=NOW)
    assert len(result.reply.text) <= 4000
    assert repo.agent_snapshot(1, now=NOW).proposal.reviewed_update_id is None
    ingest(repo, 2, 'sí')
    repo.apply_agent_control(2, now=NOW)
    assert not repo.list_lines()
