"""Synthetic isolated full-dialogue probe. Never loads settings or launches Telegram.

Verification is stdlib-only and compares literal frozen expectations, not reducers.
Offline native HTTP fixtures measure integration, NOT language understanding.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import sys
import tempfile
import traceback
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / 'docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix.json'
TEMP = Path('C:/Users/Takeshi/AppData/Local/Temp/opencode')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_matrix():
    return json.loads(MATRIX.read_text(encoding='utf-8'))


def code_hashes():
    paths = [*ROOT.glob('*.py'), *ROOT.glob('shopping_agent/**/*.py'),
             *ROOT.glob('migrations/*'), *ROOT.glob('shopping_agent/skills/*.md'),
             ROOT / 'pyproject.toml', ROOT / 'tests/guided_helpers.py',
             ROOT / 'tests/fakes.py']
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths) if p.is_file()}


def projection(state, saved):
    proposal = state['snapshot'].get('proposal')
    items = proposal['items'] if proposal else []
    question = state.get('question')
    return {
        'q': question['kind'] if question else None,
        'names': [i['description'] for i in items],
        'quantities': [i['quantity'] for i in items],
        'units': [i.get('unit') for i in items],
        'base': [i.get('base_quantity') for i in items],
        'additional': [i.get('additional_quantity') for i in items],
        'condition': proposal.get('condition') if proposal else None,
        'topic': [i['description'] for i in (state.get('topic') or {}).get('items', [])],
        'saved': [[r['description'], r['quantity']] for r in saved],
    }


def verify_step(record, step):
    """No application imports: literal expectations and independent write witnesses."""
    errors = []
    if record.get('status') != 'executed':
        return ['unexecuted: ' + record.get('error', 'previous step failed')]
    try:
        before, state = record['before'], record['state']
        observed = projection(state, record['saved_rows'])
        for key, expected in step['expect'].items():
            if observed.get(key) != expected:
                errors.append(f'quality:{key}: expected {expected!r}, observed {observed.get(key)!r}')
        if step.get('preserve'):
            for key in ('question', 'topic', 'review'):
                if before.get(key) != state.get(key):
                    errors.append(f'security:read changed {key}')
            if before['snapshot'].get('proposal') != state['snapshot'].get('proposal'):
                errors.append('security:read changed proposal/expiry')
        if (step.get('ambiguous') and
                projection(before, record['before_saved_rows'])['quantities'] != observed['quantities']):
            errors.append('security:ambiguous assignment applied')
        if step.get('reply_contains', '').casefold() not in record['reply']['text'].casefold():
            errors.append('quality:missing query response')
        results = record['model_results']
        if step.get('tool') and not step.get('allow_fallback'):
            if len(results) != 1 or results[0]['reason'] != 'candidate':
                errors.append('quality:required interpretation fell back or was not executed')
            elif results[0]['answer']['kind'] in {'clarify', 'cancel'}:
                errors.append('quality:clarification is not understanding')
        if record['saved_rows'] != record['before_saved_rows']:
            q, witness = before.get('question') or {}, before.get('review') or {}
            proposal = before['snapshot'].get('proposal') or {}
            event = record['event']
            explicit = (record.get('selection') or {}).get('kind') == 'confirm' or (
                event.get('text', '').strip().casefold() in {'sí', 'si', 'confirmar', 'confirmo'})
            if q.get('kind') != 'review' or q.get('status') != 'active' or not explicit:
                errors.append('security:write before separate final confirmation')
            if (not witness.get('delivered_message_id') or not any(
                    d['message_id'] == witness['delivered_message_id']
                    and d['digest'] == witness['summary_digest'] for d in record['before_deliveries'])):
                errors.append('security:write without actual delivery receipt')
            if event['update_id'] <= witness.get('source_update_id', event['update_id']):
                errors.append('security:confirmation not posterior to review')
            if datetime.fromisoformat(proposal['expires_at']) <= datetime.fromisoformat(record['now']):
                errors.append('security:expired confirmation wrote')
            text = q['text']
            if (len(text.encode('utf-16-le')) // 2 > 4000
                    or hashlib.sha256(text.encode()).hexdigest() != witness['summary_digest']
                    or witness['proposal_id'] != proposal['id']
                    or witness['revision'] != proposal['revision']
                    or witness['question_id'] != q['id']
                    or q['proposal_revision'] != proposal['revision']):
                errors.append('security:complete current review witness mismatch')
            for item in proposal.get('items', []):
                if item.get('internal_conflicts') and item.get('duplicate_decision') is None:
                    errors.append('security:internal duplicate without decision')
                if item.get('quantity') is None:
                    errors.append('security:unknown quantity saved')
                target = (item.get('target') or {}).get('id')
                if target in {r['line_id'] for r in before['snapshot'].get('reservations', [])}:
                    errors.append('security:reserved target saved')
                if item.get('requires_explicit_unit') and item.get('unit') is None:
                    errors.append('security:required unit missing')
                if item.get('kind') == 'increment' and (
                    item.get('base_quantity') is None or item.get('additional_quantity') is None
                    or item['quantity'] != item['base_quantity'] + item['additional_quantity']):
                    errors.append('security:increment is not base+additional=total')
        for index, call in enumerate(record['http']):
            request = json.loads(call['request'])
            if request['model'] != load_matrix()['model'] or request['think'] is not False or (
                request['options'] != {'temperature': 0, 'num_ctx': 8192, 'num_predict': 512}):
                errors.append('security:model parameters changed')
            context = {k: request[k] for k in ('messages', 'tools')}
            if len(json.dumps(context, ensure_ascii=False, separators=(',', ':')).encode()) > 24000:
                errors.append('security:context budget exceeded')
            # Independently reject raw malformed/truncated/refused output even when a
            # fabricated application validation record labels it a valid candidate.
            if index < len(results) and results[index]['reason'] == 'candidate':
                response = json.loads(call['response'])
                native = response.get('message', {})
                tools = native.get('tool_calls', [])
                if (call['status'] != 200 or response.get('done') is not True
                        or response.get('done_reason') != 'stop' or native.get('refusal')
                        or len(tools) != 1):
                    errors.append('quality:raw output invalid despite candidate validation')
                else:
                    function = tools[0]['function']
                    offered = {t['function']['name'] for t in request['tools']}
                    if function['name'] not in offered or type(function['arguments']) is not dict:
                        errors.append('quality:raw unoffered or invalid native tool')
        # Overflow/invalid history may make no HTTP call, but cannot count as understanding.
        if len(results) != len(record['http']) and any(r['reason'] == 'candidate' for r in results):
            errors.append('quality:candidate without matching raw HTTP evidence')
        if step.get('replay') and not record.get('replay_identical'):
            errors.append('security:replay changed reply')
        if len(record['http']) > 4 or any(r['tool_calls'] > 8 for r in results):
            errors.append('security:call budget exceeded')
        if record.get('orders_changed'):
            errors.append('security:synthetic purchase fixture changed')
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f'invalid evidence: {type(exc).__name__}: {exc}')
    return errors


def verify_file(path):
    """Recalculate every oracle and completeness independently; no model/network/DB."""
    errors, records = [], []
    try:
        records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        manifest = records[0]
        matrix = load_matrix()
        for key, value in {'matrix_hash': digest(MATRIX), 'frozen_matrix': matrix,
                           'script_hash': digest(Path(__file__)),
                           'code_hashes': code_hashes(), 'parameters': matrix['parameters'],
                           'model': matrix['model'], 'repetitions': 3}.items():
            if manifest.get(key) != value:
                errors.append(f'manifest mismatch: {key}')
        if manifest.get('type') != 'manifest' or manifest.get('mode') not in {'offline', 'real'}:
            errors.append('invalid manifest')
        expected = {(c['id'], p, r, n): step for c in matrix['cases'] for p in c['paths']
                    for r in range(1, 4) for n, step in enumerate(c['steps'], 1)}
        seen, outcomes = set(), {}
        for record in records[1:]:
            key = (record.get('case'), record.get('path'), record.get('repetition'), record.get('step'))
            if key not in expected or key in seen:
                errors.append(f'unexpected/duplicate record: {key}')
                continue
            seen.add(key)
            step = expected[key]
            if record.get('input') != {k: v for k, v in step.items() if k != 'expect'}:
                errors.append(f'input mismatch: {key}')
            failures = verify_step(record, step)
            outcomes[key] = failures
            errors.extend(f'{key}: {e}' for e in failures)
        errors.extend(f'missing step: {key}' for key in expected.keys() - seen)
        groups = {}
        for group in ('bounded', 'security', 'general-free'):
            conversations = {(c['id'], p, r) for c in matrix['cases'] if c['group'] == group
                             for p in c['paths'] for r in range(1, 4)}
            passed = sum(all(key in seen and not outcomes.get(key) for key in expected
                             if key[:3] == conversation) for conversation in conversations)
            groups[group] = {'passed': passed, 'total': len(conversations)}
        totals = Counter(record.get('status') for record in records[1:])
        fallbacks = Counter('clarify_candidate' if result['reason'] == 'candidate' else result['reason']
                            for record in records[1:]
                            for result in record.get('model_results', []) if result['reason'] != 'candidate'
                            or (result.get('answer') or {}).get('kind') == 'clarify')
        return {'accepted': not errors, 'errors': errors, 'groups': groups,
                'steps': dict(totals), 'fallbacks': dict(fallbacks),
                'security_failures': sum('security:' in e for e in errors),
                'model_turns': sum(len(r.get('model_results', [])) for r in records[1:]),
                'simulated_button_steps': sum(bool(r.get('selection')) for r in records[1:])}
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return {'accepted': False, 'errors': [f'invalid evidence: {type(exc).__name__}: {exc}']}


def prohibit_private(event, args):
    if event == 'import' and args[0] in {'config', 'runtime', 'cli'}:
        raise PermissionError('Probe must not import configuration or runtime launchers')
    if event == 'open' and 'private' in str(args[0]).lower():
        raise PermissionError('Probe must not access private paths')


async def run_probe(mode, output):
    # Imports deliberately lazy: --verify has no application/transport imports.
    import httpx

    from conversation import Conversation
    from shopping_agent.guided_conversation import GuidedConversation
    from shopping_agent.guided_ollama import GuidedOllamaAgent
    from telegram_io import TelegramIO
    from tests.fakes import FakeBot
    from tests.guided_helpers import PurchaseBlockedConversation, PurchaseBlockedRepository, message

    class CommandsOnly:
        async def parse(self, text, lines):
            from interpreter import clarify
            return clarify()

    class ProbeBot(FakeBot):
        def __init__(self):
            super().__init__()
            self.acks, self.receipts = [], []

        async def answer_callback_query(self, *, callback_query_id):
            self.acks.append(callback_query_id)

        async def get_me(self):
            from telegram import User
            return User(id=99, is_bot=True, first_name='Synthetic bot')

        async def send_message(self, *, chat_id, text, **kwargs):
            sent = await super().send_message(chat_id=chat_id, text=text, **kwargs)
            markup = kwargs.get('reply_markup')
            self.receipts.append({'request': {'chat_id': chat_id, 'text': text,
                'keyboard': markup.to_dict() if markup else None}, 'response': sent.to_dict()})
            return sent

        def receive_callback(self, number, token, message_id):
            from telegram import Update
            self.updates.append(Update.de_json({'update_id': number, 'callback_query': {
                'id': f'synthetic-{number}', 'chat_instance': 'synthetic', 'data': token,
                'from': {'id': 7, 'is_bot': False, 'first_name': 'Synthetic owner'},
                'message': {'message_id': message_id, 'date': 1,
                    'chat': {'id': 7, 'type': 'private'},
                    'from': {'id': 99, 'is_bot': True, 'first_name': 'Synthetic bot'}}}}, None))

    matrix = load_matrix()
    manifest = {'type': 'manifest', 'mode': mode, 'model': matrix['model'],
                'parameters': matrix['parameters'], 'repetitions': 3,
                'matrix_hash': digest(MATRIX), 'script_hash': digest(Path(__file__)),
                'frozen_matrix': matrix,
                'code_hashes': code_hashes(), 'started_at': datetime.now(UTC).isoformat(),
                'transport': 'synthetic Telegram stub; no Telegram network',
                'offline': 'native HTTP fixtures, NOT language understanding'}
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError('Evidence is immutable: choose a new output path')
    with output.open('x', encoding='utf-8') as file:
        def emit(record):
            file.write(json.dumps(record, ensure_ascii=False) + '\n')
            file.flush()

        if mode == 'real':
            try:
                async with httpx.AsyncClient(trust_env=False, timeout=5) as client:
                    response = await client.get('http://127.0.0.1:11434/api/tags')
                    response.raise_for_status()
                    available = [m for m in response.json()['models'] if m.get('name') == matrix['model']]
                    manifest['availability'] = available
                    if not available:
                        raise RuntimeError('Fixed E4B model not present; no download authorized')
            except (httpx.HTTPError, ValueError, RuntimeError, KeyError) as exc:
                manifest['blocker'] = str(exc)
                emit(manifest)
                for case in matrix['cases']:
                    for path in case['paths']:
                        for repetition in range(1, 4):
                            for number, step in enumerate(case['steps'], 1):
                                emit({'case': case['id'], 'path': path, 'repetition': repetition,
                                      'step': number, 'status': 'unexecuted', 'error': str(exc),
                                      'input': {k: v for k, v in step.items() if k != 'expect'}})
                return
        emit(manifest)
        for case in matrix['cases']:
            for path in case['paths']:
                for repetition in range(1, 4):
                    with tempfile.TemporaryDirectory(dir=TEMP, prefix='guided-acceptance-') as directory:
                        repo = PurchaseBlockedRepository(Path(directory) / 'synthetic.db')
                        repo.migrate()
                        now = datetime.now(UTC)
                        bot = ProbeBot()
                        io = TelegramIO(bot, repo, 7)
                        calls, results = [], []
                        fixture = None
                        network = httpx.AsyncHTTPTransport()

                        # Each conversation is awaited and destroyed before the next loop iteration;
                        # these closures intentionally observe its current turn fixture and clock.
                        async def respond(request):
                            call = {'url': str(request.url), 'method': request.method,
                                    'request': request.content.decode('utf-8'),
                                    'request_base64': base64.b64encode(request.content).decode()}
                            calls.append(call)  # noqa: B023
                            try:
                                if mode == 'offline':
                                    if fixture is None:  # noqa: B023
                                        raise AssertionError('Unexpected model call without frozen fixture')
                                    name, arguments = fixture  # noqa: B023
                                    response = httpx.Response(200, json={'done': True, 'done_reason': 'stop',
                                        'message': {'role': 'assistant', 'tool_calls': [{'function': {
                                            'name': name, 'arguments': arguments}}]}})
                                else:
                                    if str(request.url) != 'http://127.0.0.1:11434/api/chat':
                                        raise PermissionError('Only fixed local model endpoint is authorized')
                                    response = await network.handle_async_request(request)  # noqa: B023
                                await response.aread()
                                call.update(status=response.status_code,
                                            response=response.content.decode('utf-8', errors='replace'),
                                            response_base64=base64.b64encode(response.content).decode())
                                return response
                            except Exception as exc:
                                call['error'] = repr(exc)
                                raise

                        class RecordingAgent(GuidedOllamaAgent):
                            async def interpret(self, event, state, history):
                                result = await super().interpret(event, state, history)
                                results.append({'history': history, **result.model_dump(mode='json')})  # noqa: B023
                                return result

                        agent = RecordingAgent(matrix['model'], transport=httpx.MockTransport(respond))
                        legacy = Conversation(repo, CommandsOnly(), clock=lambda: now)  # noqa: B023
                        conversation = PurchaseBlockedConversation(repo,
                            GuidedConversation(repo, agent, legacy, clock=lambda: now))  # noqa: B023
                        if case.get('seed'):
                            repo.ingest_events([message(0, 'synthetic saved-row fixture')], 1)
                            from domain import Reply
                            repo.complete_agent_reply(0, Reply(text='Synthetic fixture, not a purchase.'))
                            with repo._connection(write=True) as db:
                                for index, (name, quantity) in enumerate(case['seed']):
                                    db.execute('INSERT INTO list_lines VALUES (?,?,?,?,1,0)',
                                               (f'seed-{index}', None, name, quantity))
                                if case.get('reserve_seed'):
                                    db.execute("INSERT INTO orders(id,source_update_id,mode,created_at) "
                                               "VALUES ('synthetic-reserved',0,'dry_run',?)", (now.isoformat(),))
                                    for index in case['reserve_seed']:
                                        db.execute("INSERT INTO reservations VALUES (?,'synthetic-reserved')",
                                                   (f'seed-{index}',))

                        def rows():
                            return [r.model_dump(mode='json') for r in repo.list_lines()]  # noqa: B023

                        def deliveries():
                            with repo._connection() as db:  # noqa: B023
                                return [dict(r) for r in db.execute('SELECT * FROM telegram_deliveries')]

                        def orders():
                            with repo._connection() as db:  # noqa: B023
                                return [dict(r) for r in db.execute('SELECT * FROM orders')]

                        initial_orders = orders()
                        failed, previous_event = None, None
                        previous_reply = None
                        for number, step in enumerate(case['steps'], 1):
                            record = {'case': case['id'], 'group': case['group'], 'path': path,
                                      'repetition': repetition, 'step': number,
                                      'input': {k: v for k, v in step.items() if k != 'expect'}}
                            if failed:
                                emit({**record, 'status': 'unexecuted', 'error': failed})
                                continue
                            calls.clear()
                            results.clear()
                            fixture = step.get('tool')
                            now += timedelta(seconds=step.get('advance_seconds', 0))
                            record['now'] = now.isoformat()
                            event = None
                            try:
                                selection = None
                                if step.get('replay'):
                                    event = previous_event
                                elif step.get('choice'):
                                    state = repo.guided_state(previous_event.update_id, now=now)
                                    choices = state.question.choices
                                    index = next(i for i, c in enumerate(choices) if c.kind == step['choice']
                                        and ('positions' not in step or list(c.positions) == step['positions'])
                                        and ('unit' not in step or c.unit == step['unit']))
                                    choice = choices[index]
                                    if path == 'button':
                                        with repo._connection() as db:
                                            row = db.execute('SELECT token,notice_id FROM guided_tokens WHERE question_id=? '
                                                'AND question_version=? AND choice_index=?',
                                                (str(state.question.id), state.question.version, index)).fetchone()
                                            receipt = db.execute('SELECT message_id FROM telegram_deliveries '
                                                'WHERE notice_id=? ORDER BY rowid DESC LIMIT 1', (row[1],)).fetchone()
                                        selection = choice.model_dump(mode='json')
                                        bot.receive_callback(number, row[0],
                                            999999 if step.get('unknown_delivery') else receipt[0])
                                        await io.poll_once()
                                        event, _ = repo.event_result(number)
                                        record['selection_label'] = 'SIMULATED BUTTON, not model comprehension'
                                    else:
                                        text = choice.label if step.get('text_from_choice') else step['text']
                                        bot.receive(number, text)
                                        await io.poll_once()
                                        event, _ = repo.event_result(number)
                                else:
                                    bot.receive(number, step['text'])
                                    await io.poll_once()
                                    event, _ = repo.event_result(number)
                                before = repo.guided_state(event.update_id, now=now).model_dump(mode='json')
                                record.update(before=before, before_saved_rows=rows(),
                                              before_deliveries=deliveries(), event=event.model_dump(mode='json'),
                                              selection=selection, now=now.isoformat())
                                reply = await conversation.handle(event, 'dry_run')
                                if step.get('deliver', True):
                                    await io.send_pending()
                                after = repo.guided_state(event.update_id, now=now).model_dump(mode='json')
                                record.update(status='executed', state=after, saved_rows=rows(),
                                              deliveries=deliveries(), reply=reply.model_dump(mode='json'),
                                              model_results=list(results), http=list(calls),
                                              orders_changed=orders() != initial_orders,
                                              stub_sent=list(bot.sent), callback_acks=list(bot.acks),
                                              transport_receipts=list(bot.receipts),
                                              replay_identical=not step.get('replay')
                                              or reply == previous_reply)
                                record['validation'] = verify_step(record, step)
                                if record['validation']:
                                    failed = '; '.join(record['validation'])
                                previous_event, previous_reply = event, reply
                            except Exception as exc:  # noqa: BLE001 - preserve raw failed turn and later steps
                                failed = f'{type(exc).__name__}: {exc}'
                                current = event or previous_event
                                record.update(status='failed', error=failed, http=list(calls),
                                              model_results=list(results), saved_rows=rows(),
                                              deliveries=deliveries(), traceback=traceback.format_exc(),
                                              state=repo.guided_state(current.update_id, now=now).model_dump(mode='json')
                                              if current else None,
                                              transport_receipts=list(bot.receipts), callback_acks=list(bot.acks))
                            emit(record)
                        await network.aclose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['offline', 'real'], default='offline')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--repetitions', type=int, choices=[3], default=3)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    sys.addaudithook(prohibit_private)
    if args.verify:
        result = verify_file(args.verify)
    else:
        if args.output is None:
            parser.error('--output required unless --verify is given')
        asyncio.run(run_probe(args.mode, args.output))
        result = verify_file(args.output)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
