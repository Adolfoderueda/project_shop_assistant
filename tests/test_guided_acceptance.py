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
RECORD = {
    'status': 'executed', 'input': {'text': 'sí', 'choice': 'confirm'},
    'event': {'kind': 'message', 'text': 'sí', 'update_id': 2},
    'before': {'snapshot': {'proposal': {
        'id': 'draft', 'revision': 1, 'expires_at': '2026-10-09T12:15:00Z',
        'items': [{'description': 'leche', 'quantity': 2, 'internal_conflicts': [],
                   'duplicate_decision': None, 'kind': 'add'}]}},
        'question': {'id': 'question', 'kind': 'review', 'status': 'active',
                     'proposal_id': 'draft', 'proposal_revision': 1, 'text': 'Review: leche 2'}, 'topic': None,
        'review': {'delivered_message_id': 1, 'source_update_id': 1,
                   'proposal_id': 'draft', 'revision': 1, 'question_id': 'question',
                   'summary_digest': '812971e85e90173248189206caeb9da19b13251bcde4e05f3f4623840cc86f84'}},
    'state': {'snapshot': {'proposal': None}, 'question': None, 'topic': None, 'review': None},
    'before_saved_rows': [], 'saved_rows': [{'description': 'leche', 'quantity': 2}],
    'before_deliveries': [{'message_id': 1,
        'digest': '812971e85e90173248189206caeb9da19b13251bcde4e05f3f4623840cc86f84'}], 'deliveries': [],
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
