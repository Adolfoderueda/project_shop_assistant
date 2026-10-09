"""Acceptance evidence must fail closed without trusting controller-computed oracles."""

import copy
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def probe():
    path = ROOT / 'scripts/probe_guided_questions.py'
    assert path.exists(), 'Acceptance verifier is not implemented'
    spec = importlib.util.spec_from_file_location('guided_probe', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Literal independent fixture: one separate final confirmation after a delivered review.
STEP = {'text': 'sí', 'choice': 'confirm',
        'expect': {'q': None, 'quantities': [], 'saved': [['leche', 2]]}}
SUMMARY = ('Petición original: leche dos\nPropuesta (fuera de la lista guardada):\n'
           '1. alta nueva: leche: 2 envases.\nPendiente, sin guardar. ¿Confirmas?\n'
           'Confirmar / Corregir / Cancelar')
WITNESS = {'delivered_message_id': 1, 'source_update_id': 1, 'notice_id': 'notice',
           'proposal_id': 'draft', 'revision': 1, 'question_id': 'question',
           'summary_digest': 'c5e33f3251ed1222ef4072116812aca023186a1026d72f002ea7d380b89e3ed8'}
RECORD = {
    'status': 'executed', 'input': {'text': 'sí', 'choice': 'confirm'},
    'event': {'kind': 'message', 'text': 'sí', 'update_id': 2, 'user_id': 7, 'chat_id': 7},
    'before': {'snapshot': {'proposal': {
        'id': 'draft', 'revision': 1, 'expires_at': '2026-10-09T12:15:00Z',
        'original_text': 'leche dos', 'review': WITNESS,
        'items': [{'position': 1, 'description': 'leche', 'quantity': 2, 'internal_conflicts': [],
                   'duplicate_decision': None, 'kind': 'add'}]}},
        'question': {'id': 'question', 'kind': 'review', 'status': 'active',
                     'proposal_id': 'draft', 'proposal_revision': 1, 'text': SUMMARY,
                     'created_at': '2026-10-09T11:59:00Z', 'expires_at': '2026-10-09T12:15:00Z'},
        'topic': None, 'review': WITNESS},
    'state': {'snapshot': {'proposal': None}, 'question': None, 'topic': None, 'review': None},
    'before_saved_rows': [], 'saved_rows': [{'description': 'leche', 'quantity': 2}],
    'before_deliveries': [{'message_id': 1, 'notice_id': 'notice', 'chat_id': 7,
        'digest': 'c5e33f3251ed1222ef4072116812aca023186a1026d72f002ea7d380b89e3ed8'}], 'deliveries': [],
    'transport_receipts': [{'request': {'chat_id': 7, 'text': SUMMARY},
        'response': {'message_id': 1, 'chat': {'id': 7, 'type': 'private'},
                     'from': {'id': 99, 'is_bot': True}, 'text': SUMMARY}}],
    'model_results': [], 'http': [], 'reply': {'text': 'Guardado'},
    'now': '2026-10-09T12:00:00Z', 'selection': None,
}


def test_literal_delivered_confirmation_passes():
    assert probe().verify_step(RECORD, STEP) == []


@pytest.mark.parametrize('damage', ['quantity', 'premature', 'duplicate', 'delivery'])
def test_real_verifier_rejects_corrupted_evidence(damage):
    record = copy.deepcopy(RECORD)
    if damage == 'quantity':
        record['saved_rows'][0]['quantity'] = 99
    elif damage == 'premature':
        record['before']['question']['kind'] = 'quantity_single'
        record['input'] = {'text': 'dos'}
        record['event']['text'] = 'dos'
    elif damage == 'duplicate':
        record['before']['snapshot']['proposal']['items'][0]['internal_conflicts'] = [2]
    else:
        record['before_deliveries'] = []
    assert probe().verify_step(record, STEP), damage


def test_invalid_model_output_cannot_pass_matching_controller_state():
    step = {'text': 'dos', 'tool': ['responder_cantidad', {'quantity': 2}],
            'expect': {'q': None, 'quantities': [], 'saved': [['leche', 2]]}}
    record = copy.deepcopy(RECORD)
    record['model_results'] = [{'reason': 'invalid', 'answer': {'kind': 'clarify'}}]
    assert probe().verify_step(record, step)


def test_raw_invalid_envelope_cannot_be_laundered_as_validated_candidate():
    import json
    step = {'text': 'dos', 'tool': ['responder_cantidad', {'quantity': 2}],
            'expect': {'q': None, 'quantities': [], 'saved': [['leche', 2]]}}
    record = copy.deepcopy(RECORD)
    record['model_results'] = [{'reason': 'candidate', 'answer': {'kind': 'quantity'}, 'tool_calls': 1}]
    record['http'] = [{'request': json.dumps({'model': 'gemma4:e4b-it-q4_K_M', 'think': False,
        'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 512},
        'messages': [], 'tools': []}), 'response': '{"done": false}', 'status': 200}]
    assert probe().verify_step(record, step)


def test_complete_summary_digest_and_revision_cannot_be_forged():
    record = copy.deepcopy(RECORD)
    record['before']['question']['text'] = 'Truncated summary'
    record['before']['review']['revision'] = 99
    assert probe().verify_step(record, STEP)


def test_import_and_verification_do_not_load_private_configuration(tmp_path):
    probe()
    # Deny imports and file opens before loading the actual module, in a fresh interpreter.
    source = '''
import importlib.util, sys
from pathlib import Path
def audit(event, args):
    if event == 'import' and args[0] in {'config', 'runtime', 'cli'}:
        raise AssertionError('private configuration import')
    if event == 'open' and 'private' in str(args[0]).lower():
        raise AssertionError('private file access')
sys.addaudithook(audit)
spec = importlib.util.spec_from_file_location('probe', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.verify_file(Path(sys.argv[2]))['errors']
'''
    invalid = tmp_path / 'invalid.jsonl'
    invalid.write_text('{}\n', encoding='utf-8')
    result = subprocess.run([sys.executable, '-P', '-c', source,
                             str(ROOT / 'scripts/probe_guided_questions.py'), str(invalid)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_cli_independent_verifier_nonzero_for_invalid_file(tmp_path):
    probe()
    invalid = tmp_path / 'invalid.jsonl'
    invalid.write_text('{}\n', encoding='utf-8')
    result = subprocess.run([sys.executable, '-P', str(ROOT / 'scripts/probe_guided_questions.py'),
                             '--verify', str(invalid)], capture_output=True, text=True, check=False)
    assert result.returncode != 0


def test_frozen_matrix_is_complete_and_not_controller_derived():
    module = probe()
    matrix = module.load_matrix()
    assert matrix['repetitions'] == 3
    assert {'bounded', 'security', 'general-free'} == {c['group'] for c in matrix['cases']}
    for case in matrix['cases']:
        assert case['steps'][-1]['expect']['q'] is None
        for step in case['steps']:
            assert {'q', 'quantities', 'saved'} <= step['expect'].keys()


def test_verifier_rejects_missing_later_steps_and_hash_mismatch(tmp_path):
    module = probe()
    import json
    file = tmp_path / 'incomplete.jsonl'
    file.write_text(json.dumps({'type': 'manifest', 'matrix_hash': 'wrong'}) + '\n',
                    encoding='utf-8')
    result = module.verify_file(file)
    assert result['errors']
    assert not result['accepted']


@pytest.mark.parametrize('case_id', ['shared', 'query-then-answer'])
def test_harness_uses_callback_ack_and_actual_question_message(tmp_path, monkeypatch, case_id):
    import asyncio
    import json
    module = probe()
    matrix = module.load_matrix()
    matrix['cases'] = [c for c in matrix['cases'] if c['id'] == case_id]
    monkeypatch.setattr(module, 'load_matrix', lambda: matrix)
    output = tmp_path / 'trace.jsonl'
    asyncio.run(module.run_probe('offline', output))
    records = [json.loads(line) for line in output.read_text(encoding='utf-8').splitlines()[1:]]
    assert all(r['status'] == 'executed' and not r['validation'] for r in records), [
        (r['path'], r['step'], r.get('error'), r.get('validation')) for r in records
        if r['status'] != 'executed' or r.get('validation')]


EVIDENCE = ROOT / 'docs/superpowers/evidence/2026-10-09-preguntas-guiadas'


def archived_step(case_id, step_number):
    """Use immutable actual transport/model traces; expectations remain literal matrix data."""
    import json
    records = [json.loads(line) for line in (EVIDENCE / 'offline-v2.jsonl').read_text(
        encoding='utf-8').splitlines()]
    record = next(r for r in records[1:] if r['case'] == case_id and r['path'] == 'button'
                  and r['repetition'] == 1 and r['step'] == step_number)
    case = next(c for c in records[0]['frozen_matrix']['cases'] if c['id'] == case_id)
    return record, case['steps'][step_number - 1]


def replace_raw_response(record, mutate):
    import base64
    import json
    call = record['http'][0]
    raw = json.loads(call['response'])
    mutate(raw['message']['tool_calls'][0]['function']['arguments'])
    call['response'] = json.dumps(raw, ensure_ascii=False)
    call['response_base64'] = base64.b64encode(call['response'].encode()).decode()


@pytest.mark.parametrize('arguments', [
    {'quantity': 'NOT_A_NUMBER'}, {'quantity': True}, {'quantity': 0}, {'quantity': -1},
    {'quantity': 9223372036854775808}, {}, {'quantity': 2, 'injected': 'save'},
    {'quantity': 2, 'unit': 'kg'},
])
def test_raw_schema_corruption_cannot_pass_claimed_candidate(arguments):
    record, step = archived_step('shared', 3)
    assert probe().verify_step(record, step) == []
    replace_raw_response(record, lambda args: (args.clear(), args.update(arguments)))
    assert any('schema' in e for e in probe().verify_step(record, step))


def test_valid_raw_quantity_must_reconcile_with_recorded_decoded_candidate():
    record, step = archived_step('shared', 3)
    replace_raw_response(record, lambda args: args.update(quantity=3))
    assert any('decoded' in e for e in probe().verify_step(record, step))


@pytest.mark.parametrize('field,value', [('quantity', 2.0), ('source_update_id', 3.0)])
def test_decoded_candidate_reconciliation_does_not_coerce_types(field, value):
    record, step = archived_step('shared', 3)
    answer = record['model_results'][0]['answer']
    if field == 'quantity':
        answer['patches'][0][field] = value
    else:
        answer[field] = value
    assert any('decoded' in e for e in probe().verify_step(record, step))


def counterfeit_summary(record, text, *, transport=False):
    import hashlib
    witness = record['before']['review']
    witness['summary_digest'] = hashlib.sha256(text.encode()).hexdigest()
    record['before']['snapshot']['proposal']['review'] = copy.deepcopy(witness)
    record['before']['question']['text'] = text
    for receipt in record['before_deliveries']:
        if receipt['message_id'] == witness['delivered_message_id']:
            receipt['digest'] = witness['summary_digest']
    if transport:
        for receipt in record['transport_receipts']:
            if receipt['response']['message_id'] == witness['delivered_message_id']:
                receipt['request']['text'] = receipt['response']['text'] = text


@pytest.mark.parametrize('transport', [False, True])
def test_self_consistent_controls_only_summary_is_not_a_complete_review(transport):
    record, step = archived_step('one-each', 3)
    assert probe().verify_step(record, step) == []
    counterfeit_summary(record, 'Confirmar / Corregir / Cancelar', transport=transport)
    errors = probe().verify_step(record, step)
    assert any('summary facts' in e for e in errors)
    if not transport:
        assert any('transport' in e for e in errors)


@pytest.mark.parametrize('field', ['request_text', 'response_text', 'message_id', 'chat_id'])
def test_actual_transport_receipt_must_match_delivered_review(field):
    record, step = archived_step('one-each', 3)
    message = record['before']['review']['delivered_message_id']
    receipt = next(r for r in record['transport_receipts'] if r['response']['message_id'] == message)
    if field == 'request_text':
        receipt['request']['text'] = 'Different request'
    elif field == 'response_text':
        receipt['response']['text'] = 'Different response'
    elif field == 'message_id':
        receipt['response']['message_id'] = 999
    else:
        receipt['response']['chat']['id'] = 999
    assert any('transport' in e for e in probe().verify_step(record, step))


@pytest.mark.parametrize('case_id,number,omitted', [
    ('one-each', 3, '1. alta nueva: huevos: 1 envases.'),
    ('shared', 4, '2 envases'),
    ('increment', 2, 'Base + adicional = total: 2 + 3 = 5 envases.'),
    ('reservation', 3, 'Origen seleccionado: seed-1, revisión 1.'),
    ('replacement', 2, 'Sustituir leche por arroz'),
    ('internal-duplicates', 4, 'Decisión de duplicado: línea separada; no se suman ni fusionan.'),
])
def test_summary_independently_contains_every_proposal_fact(case_id, number, omitted):
    record, step = archived_step(case_id, number)
    assert probe().verify_step(record, step) == []
    text = record['before']['question']['text']
    assert omitted in text
    counterfeit_summary(record, text.replace(omitted, 'OMITTED'), transport=True)
    assert any('summary facts' in e for e in probe().verify_step(record, step))


def test_summary_quantity_fact_cannot_use_bool_as_one():
    record, step = archived_step('one-each', 3)
    record['before']['snapshot']['proposal']['items'][0]['quantity'] = True
    record['saved_rows'][0]['quantity'] = True
    text = record['before']['question']['text'].replace('huevos: 1 envases', 'huevos: True envases')
    counterfeit_summary(record, text, transport=True)
    assert any('summary facts' in e for e in probe().verify_step(record, step))


@pytest.mark.parametrize('expired', ['question', 'proposal', 'question_after_proposal'])
def test_both_question_and_proposal_must_be_live_with_bounded_expiry(expired):
    record, step = archived_step('one-each', 3)
    if expired == 'question_after_proposal':
        record['before']['question']['expires_at'] = '2099-01-01T00:00:00Z'
    else:
        target = (record['before']['question'] if expired == 'question'
                  else record['before']['snapshot']['proposal'])
        target['expires_at'] = '2000-01-01T00:00:00Z'
    assert any('expir' in e for e in probe().verify_step(record, step))


def test_archive_integrity_distinguishes_recorded_probe_from_current_verifier():
    result = probe().verify_file(EVIDENCE / 'offline-v2.jsonl')
    assert result.get('integrity', {}).get('archived_source_commit') == (
        '6bf409ceed110104f3aa1e1fb6e75ad311dd27ca')
    assert result['integrity']['recorded_runtime_verified'] is True
    assert result['integrity']['recorded_probe_sha256'] == (
        '5496d090e75e06e4b524dced7866a1d27bfd146c432e887f6455ab9fd5683278')


def test_duplicate_raw_json_key_cannot_hide_a_bad_quantity():
    import base64
    record, step = archived_step('shared', 3)
    call = record['http'][0]
    assert '"quantity":2' in call['response']
    call['response'] = call['response'].replace('"quantity":2',
        '"quantity":"NOT_A_NUMBER","quantity":2')
    call['response_base64'] = base64.b64encode(call['response'].encode()).decode()
    assert probe().verify_step(record, step)


def test_frozen_offered_schema_cannot_be_relaxed_in_recorded_request():
    import json
    record, step = archived_step('shared', 3)
    request = json.loads(record['http'][0]['request'])
    schema = next(t['function']['parameters'] for t in request['tools']
                  if t['function']['name'] == 'responder_cantidad')
    schema['properties']['quantity'] = {'type': 'string'}
    record['http'][0]['request'] = json.dumps(request)
    assert any('schema' in e for e in probe().verify_step(record, step))


def test_archived_exact_source_hash_still_rejects_changed_newline_metadata(tmp_path, monkeypatch):
    import json
    module = probe()
    metadata = json.loads(module.ARCHIVE_METADATA.read_text(encoding='utf-8'))
    metadata['newline_map']['config.py']['crlf_bitmap'] = 'AAAA'  # Literal wrong execution bytes.
    corrupted = tmp_path / 'archive.json'
    corrupted.write_text(json.dumps(metadata), encoding='utf-8')
    monkeypatch.setattr(module, 'ARCHIVE_METADATA', corrupted)
    result = module.verify_file(EVIDENCE / 'offline-v2.jsonl')
    assert not result['accepted']
    assert any('newline' in e or 'source bytes' in e for e in result['errors'])


def test_archive_raw_mutation_fails_integrity_without_exempting_step_oracle(tmp_path):
    import json
    module = probe()
    records = [json.loads(line) for line in (EVIDENCE / 'offline-v2.jsonl').read_text(
        encoding='utf-8').splitlines()]
    record = next(r for r in records[1:] if r['case'] == 'shared' and r['path'] == 'button'
                  and r['repetition'] == r['step'] == 3)
    replace_raw_response(record, lambda args: args.update(quantity='NOT_A_NUMBER'))
    file = tmp_path / 'mutated.jsonl'
    file.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in records) + '\n', encoding='utf-8')
    result = module.verify_file(file)
    assert not result['accepted']
    assert any('archived raw artifact changed' in e for e in result['errors'])
    assert any('native schema invalid' in e for e in result['errors'])
