"""HTTP-simulated boundary acceptance, NOT real language/model quality."""

import asyncio

import pytest


def run_case(tmp_path, name):
    from scripts.probe_skills_agent import run_case
    return asyncio.run(run_case(tmp_path, name, offline=True))


def test_runtime_multi_product_flow_needs_confirm(tmp_path):
    records = run_case(tmp_path, 'weekly')
    assert all(r['pass'] for r in records)
    assert records[0]['after']['lines'] == []
    assert records[2]['after']['lines'] == []
    assert [(r['description'], r['quantity']) for r in records[3]['after']['lines']] == [
        ('arroz', 2), ('carne', 3)]


def test_increment_selection_cancel_and_result_coverage(tmp_path):
    records = run_case(tmp_path, 'selection')
    assert all(r['pass'] for r in records)
    assert records[0]['after']['proposal']['reviewed_revision'] is None
    assert records[1]['after']['proposal']['items'][0]['quantity'] == 5
    assert records[1]['after']['proposal']['items'][0]['target']['id'] == 'seed-1'
    assert records[1]['after']['proposal']['items'][0]['base_quantity'] == 2
    assert records[1]['after']['proposal']['items'][0]['additional_quantity'] == 3
    assert records[-1]['after']['proposal'] is None
    assert records[-1]['after']['lines'][0]['quantity'] == 2


@pytest.mark.parametrize('name', [
    'ttl', 'changed', 'reserved', 'deleted', 'restart_replay', 'edit',
    'internal_duplicate', 'existing_duplicate', 'unknown_base', 'replace',
    'owner', 'malicious', 'atomic', 'old_jobs', 'batch_changed', 'batch_reserved', 'batch_deleted',
])
def test_atomic_conflicts_and_replays_through_real_boundaries(tmp_path, name):
    records = run_case(tmp_path, name)
    assert records and all(r['pass'] for r in records), records
