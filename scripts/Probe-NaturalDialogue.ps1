# Opt-in synthetic acceptance; never load settings or control existing services.
[CmdletBinding()]
param([string]$Python = "", [switch]$Offline, [switch]$FailExpectation,
      [switch]$TestUnavailable)
$ErrorActionPreference = "Stop"
if ($FailExpectation -and -not $Offline) { throw "-FailExpectation requires -Offline" }
$root = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $Python = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $Python)) { $Python = Join-Path $root "..\..\.venv\Scripts\python.exe" }
}
# ASCII source works with legacy Windows PowerShell encoding.
$code = @'
import asyncio
import gc
import json
import os
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import httpx
from conversation import Conversation
from dialogue_requests import classify_request
from domain import IncomingMessage
from interpreter import parse_command
from ollama_interpreter import OllamaInterpreter
from ollama_replies import OllamaReplyWriter
from storage import Repository

offline, fail, unavailable = (value == 'True' for value in sys.argv[2:])
mode = 'OFFLINE' if offline else 'REAL'
MODEL = 'gemma4:e2b'

def emit(**record):
    print(json.dumps(record, ensure_ascii=True), flush=True)

def fixture(request):
    data = json.loads(request.content)
    context = json.loads(data['messages'][1]['content'])
    if 'text' in context:
        if 'anyOf' in data['format']:
            properties = data['format']['anyOf'][0]['properties']
            action = properties['action']['enum'][0]
            lines = []
            if properties['lines']['maxItems']:
                description = properties['lines']['items']['properties']['description']['enum'][0]
                lines = [{'description': description, 'quantity': None}]
            result = {'action': action, 'lines': lines}
        else:
            result = {'action': 'clarify', 'lines': []}
    else:
        items = data['format']['properties']['blocks']['anyOf'][0]['prefixItems']
        result = {'blocks': [{'role': item['properties']['role']['const'],
                              'text': item['properties']['text']['enum'][0]} for item in items]}
    return httpx.Response(200, json={'done': True, 'done_reason': 'stop',
        'message': {'role': 'assistant', 'content': json.dumps(result)}})

class TraceTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.events = []

    async def handle_async_request(self, request):
        payload = json.loads(request.content)
        context = json.loads(payload['messages'][1]['content'])
        event = {'provider': 'interpreter' if 'text' in context else 'writer',
                 'context': context, 'model': payload['model'], 'status': None, 'raw': None}
        self.events.append(event)
        started = time.perf_counter()
        try:
            if offline:
                response = fixture(request)
            else:
                async with httpx.AsyncHTTPTransport() as transport:
                    response = await transport.handle_async_request(request)
                    await response.aread()
            event['status'] = response.status_code
            event['raw'] = response.json()
            return response
        except Exception as error:
            event['error'] = type(error).__name__
            raise
        finally:
            event['seconds'] = round(time.perf_counter() - started, 6)

class RecordingInterpreter:
    def __init__(self, transport):
        self.model = OllamaInterpreter(MODEL, transport=transport)
        self.proposal = None

    async def parse_with_dialogue(self, *args):
        intent = await self.model.parse_with_dialogue(*args)
        self.proposal = intent.model_dump(mode='json')
        return intent

class RecordingWriter:
    def __init__(self, transport):
        self.model = OllamaReplyWriter(MODEL, transport=transport)
        self.snapshot = None
        self.accepted = None

    async def draft(self, snapshot):
        self.snapshot = snapshot.model_dump(mode='json')
        result = await self.model.draft(snapshot)
        self.accepted = result is not None
        return result

# Independent acceptance oracle transcribed from the approved brief, not provider output.
BASE = [('arroz', 1), ('ARROZ', 2), ('arroz integral', None)]
ADDED = BASE + [('avena', 2)]
INCREMENTED = [('arroz', 3), ('ARROZ', 2), ('arroz integral', None)]
SEQUENCES = {
    'A': [('hols', BASE, None, None), ('hola que tal', BASE, None, None),
          ('quiero mas arroz', BASE, 'select_line', 'increment'),
          ('cancelar', BASE, None, None), ('dame mi lista', BASE, None, 'list')],
    'B': [('necesito avena', BASE, 'add_quantity', 'add'),
          ('dame mi lista', BASE, 'add_quantity', 'list'),
          ('hola', BASE, 'add_quantity', None), ('cancelar', BASE, None, None),
          ('necesito avena', BASE, 'add_quantity', 'add'),
          ('2', ADDED, None, None), ('dame mi lista', ADDED, None, 'list')],
    'C': [('quiero m\u00e1s arroz', BASE, 'select_line', 'increment'),
          ('1', BASE, 'increment_quantity', None), ('2', BASE, 'confirm_increment', None),
          ('no', BASE, None, None),
          ('quiero m\u00e1s arroz', BASE, 'select_line', 'increment'),
          ('1', BASE, 'increment_quantity', None), ('2', BASE, 'confirm_increment', None),
          ('s\u00ed', INCREMENTED, None, None), ('dame mi lista', INCREMENTED, None, 'list')],
}

async def probe(directory):
    if unavailable:
        emit(service='unavailable fixture')
        return 2, [], []
    if not offline:
        try:
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=5) as client:
                for endpoint in ('ps', 'tags'):
                    response = await client.get('http://127.0.0.1:11434/api/' + endpoint)
                    response.raise_for_status()
                    data = response.json()
                    emit(**{'initial_' + endpoint: data})
                    if endpoint == 'tags' and MODEL not in [m.get('name', m.get('model')) for m in data['models']]:
                        return 2, [], []
        except (httpx.HTTPError, ValueError, KeyError):
            return 2, [], []
    failures, coverage = [], set()
    transport = TraceTransport()
    interpreter, writer = RecordingInterpreter(transport), RecordingWriter(transport)
    now = datetime(2026, 10, 8, 12, tzinfo=UTC)
    clock = [now]

    def new_conversation(repo):
        return Conversation(repo, interpreter, reply_writer=writer, clock=lambda: clock[0])

    def new_repo(name):
        repo = Repository(Path(directory) / (name + '.db'))
        repo.migrate()
        with closing(sqlite3.connect(repo.path)) as db:
            db.executemany('INSERT INTO list_lines VALUES (?,NULL,?,?,1,1)',
                           [('rice1', 'arroz', 1), ('rice2', 'ARROZ', 2),
                            ('integral', 'arroz integral', None)])
            db.commit()
        return repo

    async def step(repo, conversation, name, number, spec, *, replay=False, expected_expiry=None):
        text, expected_rows, expected_question, required = spec
        clock[0] += timedelta(seconds=30 if replay else 10)
        transport.events.clear()
        interpreter.proposal, writer.snapshot, writer.accepted = None, None, None
        started = time.perf_counter()
        record = dict(case=name, step=number, input=text, required_intent=required,
                      replay=replay, expected_rows=expected_rows, expected_question=expected_question,
                      orders=None, passed=False, now=clock[0].isoformat())
        try:
            message = IncomingMessage(update_id=number, user_id=7, chat_id=7, text=text)
            if not replay:
                repo.ingest_batch([message], number + 1)
            reply = await conversation.handle(message, 'dry_run')
            rows = [(line.description, line.quantity) for line in repo.list_lines()]
            state = repo.dialogue_state(7, 7, now=clock[0])
            with closing(sqlite3.connect(repo.path)) as db:
                orders = db.execute('SELECT count(*) FROM orders').fetchone()[0]
            question = state.question if state else None
            checks = {'rows': rows == expected_rows, 'question': question == expected_question,
                      'orders': orders == 0}
            if expected_expiry is not None:
                checks['ttl_not_renewed'] = state is not None and state.expires_at.isoformat() == expected_expiry
            if question == 'confirm_increment':
                checks['increment_arithmetic'] = (state.base_quantity == 1 and
                    state.additional_quantity == 2 and state.proposal_quantity == 3 and
                    state.increment_confirmed is False and state.target.id == 'rice1')
            if required:
                checks['quality'] = (interpreter.proposal is not None and
                    interpreter.proposal['action'] == required and writer.accepted is True and
                    sum(e['provider'] == 'interpreter' for e in transport.events) == 1)
                if checks['quality']:
                    coverage.add(required)
            if writer.snapshot is not None:
                checks['writer_quality'] = writer.accepted is True
            if replay:
                checks['replay_no_calls'] = not transport.events
            if name == 'A' and number in (1, 2):
                checks['no_accidental_list'] = writer.snapshot is None or writer.snapshot['act'] != 'list'
                checks['greeting_no_interpreter'] = interpreter.proposal is None
            for check, passed in checks.items():
                if not passed:
                    failures.append(f'{name}:{number}:{check}')
            record.update(rows=rows, state=state.model_dump(mode='json') if state else None,
                          question=question, orders=orders, reply=reply.text, checks=checks,
                          passed=all(checks.values()))
        except Exception as error:
            record.update(error=type(error).__name__, detail=str(error))
            failures.append(f'{name}:{number}:exception')
        request = classify_request(text)
        deterministic_kind = ('greeting' if request is not None and request.action == 'greet'
                              else 'close' if text in ('cancelar', 'no')
                              else 'alias' if parse_command(text, []) is not None else 'answer_or_replay')
        record.update(proposal=interpreter.proposal, snapshot=writer.snapshot,
                      writer_accepted=writer.accepted, writer_fallback=writer.accepted is False,
                      interpreter_calls=sum(e['provider'] == 'interpreter' for e in transport.events),
                      writer_calls=sum(e['provider'] == 'writer' for e in transport.events),
                      interpretation='model_called' if interpreter.proposal is not None else 'deterministic',
                      deterministic_kind=None if interpreter.proposal is not None else deterministic_kind,
                      requests=list(transport.events), seconds=round(time.perf_counter() - started, 6))
        emit(**record)
        return record

    for name, specs in SEQUENCES.items():
        repo = new_repo(name)
        clock[0] = now
        conversation = new_conversation(repo)
        pending_expiry = None
        for number, spec in enumerate(specs, 1):
            if name == 'C' and number == 8:
                conversation = new_conversation(repo)
                emit(restart='C:between quantity and confirmation')
            record = await step(repo, conversation, name, number, spec,
                                expected_expiry=pending_expiry if name == 'B' and number in (2, 3) else None)
            if name == 'B' and number == 1 and record.get('state') is not None:
                pending_expiry = record['state']['expires_at'].replace('Z', '+00:00')
            if name == 'C' and number == 8:
                repeated = await step(repo, new_conversation(repo), name, number, spec, replay=True)
                if repeated.get('state') != record.get('state') or repeated.get('reply') != record.get('reply'):
                    failures.append('C:8:replay_state_reply')

    # Synthetic guards on separate DBs; reservation is a fixture row, not a purchase request.
    for name in ('expiry', 'reserved', 'changed_revision'):
        repo = new_repo(name)
        clock[0] = now
        conversation = new_conversation(repo)
        for number, spec in enumerate(SEQUENCES['C'][:3], 1):
            await step(repo, conversation, name, number, spec)
        if name == 'expiry':
            clock[0] += timedelta(seconds=890)  # step advances 10: exactly TTL900
        else:
            with closing(sqlite3.connect(repo.path)) as db:
                if name == 'changed_revision':
                    db.execute('UPDATE list_lines SET revision=revision+1 WHERE id=?', ('rice1',))
                else:
                    # This isolated guard fixture deliberately bypasses FK; no order is created.
                    db.execute('INSERT INTO reservations VALUES (?,?)', ('rice1', 'synthetic-reservation'))
                db.commit()
        await step(repo, new_conversation(repo), name, 4, ('s\u00ed', BASE, None, None))
    if fail:
        failures.append('offline:injected expectation failure')
    for required in ('add', 'increment', 'list'):
        if required not in coverage:
            failures.append('coverage:' + required + ':quality')
    return int(bool(failures)), failures, sorted(coverage)

base = Path(os.environ['LOCALAPPDATA']) / 'Temp' / 'opencode'
result, failures, coverage = 1, [], []
with tempfile.TemporaryDirectory(prefix='natural-dialogue-probe-', dir=base) as directory:
    emit(mode=mode, model=MODEL, temporary_root=directory)
    try:
        result, failures, coverage = asyncio.run(probe(directory))
    except Exception as error:
        emit(error=type(error).__name__, detail=str(error), orders=None)
        failures.append('probe:exception')
    finally:
        gc.collect()
emit(status={0:'PASS', 1:'FAIL', 2:'PENDING'}[result], mode=mode, failures=failures,
     coverage=coverage, temporary_removed=not Path(directory).exists())
sys.exit(result)
'@
& $Python -P -c $code $root $Offline.IsPresent $FailExpectation.IsPresent $TestUnavailable.IsPresent
exit $LASTEXITCODE
