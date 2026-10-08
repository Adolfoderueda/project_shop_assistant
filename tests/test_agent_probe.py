"""Probe exit codes, honest oracles, and synthetic/private isolation."""

import asyncio
import builtins
import io
import json
import sqlite3
from pathlib import Path

import httpx
import pytest


def test_probe_private_sentinel_never_read(tmp_path, monkeypatch):
    from scripts.probe_skills_agent import main
    private = tmp_path / 'private'
    private.mkdir()
    sentinel = private / 'settings.json'
    sentinel.write_text('SECRET sentinel must never be opened')
    original = Path.open

    def guarded(path, *args, **kwargs):
        if 'private' in path.resolve().parts:
            pytest.fail('private file opened')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', guarded)
    def guard_open(original):
        def check(file, *args, **kwargs):
            if isinstance(file, (str, Path)) and any(
                p.casefold() == 'private' for p in Path(file).resolve().parts
            ):
                pytest.fail('private file opened via Python or SQLite')
            return original(file, *args, **kwargs)
        return check

    monkeypatch.setattr(builtins, 'open', guard_open(builtins.open))
    monkeypatch.setattr(io, 'open', guard_open(io.open))
    monkeypatch.setattr(sqlite3, 'connect', guard_open(sqlite3.connect))
    monkeypatch.chdir(tmp_path)
    output = tmp_path / 'evidence.jsonl'
    assert main(['--offline', '--output', str(output)]) == 0
    assert output.exists()
    with pytest.raises(ValueError, match='private'):
        main(['--offline', '--output', str(private / 'bad.jsonl')])


def test_offline_is_labelled_and_cannot_claim_real_quality(tmp_path, capsys):
    from scripts.probe_skills_agent import main
    output = tmp_path / 'offline.jsonl'
    assert main(['--offline', '--output', str(output)]) == 0
    records = [json.loads(line) for line in output.read_text().splitlines()]
    summary = records[-1]
    assert summary['status'] == 'PASS'
    assert summary['real_quality'] == 'NOT_TESTED'
    assert records[0]['mode'] == 'offline_http_simulated'
    assert all(json.loads(line) for line in capsys.readouterr().out.splitlines())


def test_unavailable_is_pending_not_pass(tmp_path):
    from scripts.probe_skills_agent import probe

    def unavailable(request):
        raise httpx.ConnectError('synthetic unavailable', request=request)

    result = asyncio.run(probe(tmp_path / 'pending.jsonl', availability_transport=
                               httpx.MockTransport(unavailable)))
    assert result == 2
    summary = json.loads((tmp_path / 'pending.jsonl').read_text().splitlines()[-1])
    assert summary['status'] == 'PENDING'
    assert summary['real_quality'] == 'NOT_TESTED'


@pytest.mark.parametrize('calls', [[], [{'name': 'consultar_lista', 'arguments': {}}]])
def test_wrong_interpretation_cannot_pass_by_safe_fallback(tmp_path, calls):
    from scripts.probe_skills_agent import ProbeSession
    session = ProbeSession(tmp_path / 'wrong.db', offline=True)
    record = asyncio.run(session.step('Necesito arroz y carne', calls=calls, expected={
        'tool': 'proponer_altas', 'items': [('arroz', None), ('carne', None)],
        'rows': [], 'reviewed': False,
    }))
    assert record['oracle']['action'] is False
    assert record['oracle']['interpretation'] is False
    assert record['oracle']['state'] is False
    assert record['oracle']['safety'] is True
    assert record['pass'] is False


def test_probe_requires_output_and_rejects_private_case_insensitively(tmp_path):
    from scripts.probe_skills_agent import main
    with pytest.raises(SystemExit):
        main(['--offline'])
    with pytest.raises(ValueError, match='private'):
        main(['--offline', '--output', str(tmp_path / 'PRIVATE' / 'out.jsonl')])


def test_dropped_condition_fails_even_before_confirmation(tmp_path):
    from scripts.probe_skills_agent import ProbeSession, add
    session = ProbeSession(tmp_path / 'condition.db', offline=True)
    record = asyncio.run(session.step('Añade arroz solo si está en oferta',
        calls=add([('arroz', 2)]), expected={'rows': [], 'clarify': True}))
    assert record['oracle']['interpretation'] is False
    assert record['oracle']['state'] is False
    assert record['oracle']['safety'] is True
    assert not record['pass']


def test_wrong_arguments_cannot_pass_on_correct_tool(tmp_path):
    from scripts.probe_skills_agent import ProbeSession, change
    session = ProbeSession(tmp_path / 'wrong-quantity.db', offline=True)
    session.seed('arroz', 2)
    record = asyncio.run(session.step('Tres envases más de arroz',
        calls=change('increment', 'arroz', 4), expected={
            'rows': [('arroz', 2)], 'tool': 'proponer_cambio',
            'arguments': {'kind': 'increment', 'quantity': 3},
            'items': [('arroz', 5)], 'reviewed': True,
        }))
    assert record['oracle']['action'] is True
    assert record['oracle']['arguments'] is False
    assert record['oracle']['state'] is False
    assert not record['pass']


def test_budget_overflow_keeps_complete_controller_snapshot_and_fails_quality(tmp_path):
    from scripts.probe_skills_agent import ProbeSession, call
    session = ProbeSession(tmp_path / 'budget.db', offline=True)
    rows = [(f'arroz sintético {index} ' + 'x' * 130, 1) for index in range(90)]
    for description, quantity in rows:
        session.seed(description, quantity)
    record = asyncio.run(session.step('Qué lista tengo', calls=[call('consultar_lista')],
        expected={'rows': rows, 'tool': 'consultar_lista'}))
    assert record['run']['reason'] == 'context_overflow'
    assert record['ledger'] == []  # No oversized request or truncated retry.
    assert len(record['controller_snapshot']['lines']) == 90
    assert record['oracle']['safety'] is True
    assert not record['pass']


@pytest.mark.parametrize('text', ['Lote guardado: 1 cambios confirmados.',
                                'La lista contiene arroz: 99 envases.'])
def test_reply_oracle_rejects_false_success_and_invented_query_facts(tmp_path, text):
    from scripts.probe_skills_agent import ProbeSession, call, oracle
    session = ProbeSession(tmp_path / 'reply-facts.db', offline=True)
    expected = {'rows': [], 'tool': 'consultar_lista'}
    record = asyncio.run(session.step('Qué lista tengo', calls=[call('consultar_lista')],
                                      expected=expected))
    assert record['pass']
    record['reply']['text'] = text
    assert oracle(record, expected)['reply'] is False
