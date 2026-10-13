"""Reproducible skill micro-tests: labelled simulated setup, fresh real E4B turns.

Use existing venv, python -P and explicit worktree PYTHONPATH. No model/config changes.
Each case/rep starts from a fresh temporary repository; no acceptance claim.
"""

import argparse
import asyncio
import hashlib
import tempfile
from pathlib import Path

from scripts.probe_skills_agent import (
    ProbeSession,
    add,
    call,
    change,
    digest,
    encoded,
    expectation,
    safe_output,
)
from shopping_agent.skills import load_skills
from shopping_agent.tools import tool_definitions

DRAFT_CASES = ('weekly', 'edit', 'selection_edit', 'internal_duplicate',
               'existing_duplicate', 'saved_list')
QUANTITY_CASES = ('selection_start', 'replace', 'unknown_base')


async def sample(directory, case):
    session = ProbeSession(Path(directory) / 'micro.db', offline=True)
    rows = []
    if case in {'selection_edit', 'selection_start', 'unknown_base', 'replace', 'existing_duplicate'}:
        description = 'arroz blanco' if case in {'selection_edit', 'selection_start', 'unknown_base'} else 'arroz'
        quantity = None if case == 'unknown_base' else 1 if case == 'existing_duplicate' else 2
        session.seed(description, quantity)
        rows = [(description, quantity)]
    if case in {'selection_edit', 'selection_start'}:
        session.seed('arroz integral', 4)
        rows.append(('arroz integral', 4))
    if case == 'selection_edit':
        await session.step('Quiero tres envases más de arroz', calls=change('increment', 'arroz', 3, unit='envases'),
                           expected=expectation(rows, tool='proponer_cambio', reviewed=False))
        await session.step('1', calls=[], expected=expectation(rows, reviewed=True))
    elif case in DRAFT_CASES:
        items = [('arroz', None), ('carne', None)] if case == 'weekly' else [('arroz', 2)]
        text = 'Necesito arroz y carne para la compra de la semana' if case == 'weekly' else 'Necesito dos envases de arroz'
        if case == 'internal_duplicate':
            items.append(('arroz', 3))
            text = 'Necesito dos envases de arroz y otros tres envases de arroz en otra entrada'
        if case == 'saved_list':
            items = [('lentejas', 2), ('tomate', 4)]
            text = 'Para la despensa, apunta dos envases de lentejas y cuatro de tomate'
        calls = add(items)
        if case != 'weekly':
            for item in calls[0]['arguments']['items']:
                item['unit'] = 'envases'
        await session.step(text, calls=calls, expected=expectation(rows, tool='proponer_altas', items=items,
                               reviewed=case in {'edit', 'saved_list'}))
        if case in {'internal_duplicate', 'existing_duplicate'}:
            await session.step('sí', calls=[], expected=expectation(rows, reviewed=False))
    if case == 'weekly':
        text, tool, items = 'Dos envases de arroz y tres de carne', 'completar_propuesta', [('arroz', 2), ('carne', 3)]
        expected = expectation(rows, tool=tool, items=items, reviewed=True)
    elif case == 'edit':
        text = 'Sí, pero mejor cuatro envases de arroz'
        expected = expectation(rows, tool='completar_propuesta', items=[('arroz', 4)], reviewed=True)
    elif case == 'selection_edit':
        text = 'Déjalo en cuatro envases adicionales para el primer producto'
        expected = expectation(rows, tool='completar_propuesta', items=[('arroz', 6)], reviewed=True)
    elif case in {'internal_duplicate', 'existing_duplicate'}:
        text = 'Mantén cada entrada como una línea separada, no sumes las cantidades'
        items = [('arroz', 2), ('arroz', 3)] if case == 'internal_duplicate' else [('arroz', 2)]
        expected = expectation(rows, tool='completar_propuesta', items=items, reviewed=True)
    elif case == 'saved_list':
        text = 'Muéstrame lo que ya está apuntado para comprar'
        expected = expectation(rows, tool='consultar_lista', preserve=True)
    elif case in {'selection_start', 'unknown_base'}:
        text = 'Quiero tres envases más de arroz'
        expected = expectation(rows, tool='proponer_cambio', reviewed=False, kind='increment',
                               arguments={'kind': 'increment', 'quantity': 3})
    else:
        text = 'Sustituye el arroz por cuatro envases de avena'
        expected = expectation(rows, tool='proponer_cambio', reviewed=True,
                               arguments={'kind': 'replace', 'quantity': 4, 'replacement': 'avena'})
    session.offline = False
    await session.step(text, calls=[call('consultar_lista')], expected=expected)
    return session.records


async def main(label, group):
    cases = DRAFT_CASES if group == 'draft' else QUANTITY_CASES
    records = [{'type': 'micro_metadata', 'label': label, 'group': group,
                'skills_sha256': digest(load_skills()), 'schemas_sha256': digest(tool_definitions()),
                'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'note': 'Simulated setup; five fresh real contexts per case; not full acceptance'}]
    for case in cases:
        results = []
        for rep in range(5):
            with tempfile.TemporaryDirectory(prefix='skills-micro-synthetic-') as directory:
                steps = await sample(directory, case)
            for step in steps:
                step.update({'case': case, 'rep': rep + 1, 'label': label})
            records.extend(steps)
            results.append(steps[-1]['pass'])
        print(label, case, f'{sum(results)}/5')
    output = safe_output(Path(__file__).parent / f'{label}.jsonl')
    output.write_text(''.join(encoded(record) + '\n' for record in records), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--group', choices=('draft', 'quantity'), required=True)
    args = parser.parse_args()
    asyncio.run(main(args.label, args.group))
