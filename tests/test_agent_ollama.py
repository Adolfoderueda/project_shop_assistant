import asyncio
import json
import sqlite3
from datetime import UTC, datetime

import httpx
import pytest

from domain import IncomingMessage
from shopping_agent.tools import AgentTools
from storage import Repository

NOW = datetime(2026, 10, 8, tzinfo=UTC)


@pytest.fixture
def context(tmp_path):
    repo = Repository(tmp_path / 'agent.db')
    repo.migrate()
    message = IncomingMessage(update_id=1, user_id=7, chat_id=7,
                              text='Necesito arroz y carne para la compra de la semana')
    repo.ingest_batch([message], 2)
    return repo, message, AgentTools(repo, message, now=NOW)


def call(name, arguments=None):
    return {'function': {'name': name, 'arguments': arguments or {}}}


def response(calls=None, content='Éxito inventado: guardado y comprado'):
    message = {'role': 'assistant', 'content': content}
    if calls is not None:
        message['tool_calls'] = calls
    return {'model': 'gemma4:e4b-it-q4_K_M', 'created_at': '2026-10-08T00:00:00Z',
            'message': message, 'done': True, 'done_reason': 'stop'}


def run(context, handler):
    from shopping_agent.ollama import OllamaShoppingAgent
    _, message, tools = context
    return asyncio.run(OllamaShoppingAgent(transport=httpx.MockTransport(handler)).run(message, tools))


def test_native_payload_contains_original_text_and_all_skills(context):
    from shopping_agent.skills import load_skills
    def handler(request):
        assert str(request.url) == 'http://127.0.0.1:11434/api/chat'
        assert request.method == 'POST'
        data = json.loads(request.content)
        assert data['model'] == 'gemma4:e4b-it-q4_K_M'
        assert data['stream'] is False and data['think'] is False
        assert data['options'] == {'temperature': 0, 'num_ctx': 8192, 'num_predict': 512}
        assert 'format' not in data
        assert any(m['role'] == 'user' and m['content'] == context[1].text for m in data['messages'])
        assert load_skills() in data['messages'][0]['content']
        assert len(data['tools']) == 7
        raw = request.content.decode()
        for forbidden in ('user_id', 'chat_id', 'reviewed_revision', 'reviewed_update_id',
                          'Settings', 'token', 'address', 'agent.db', 'C:\\Users'):
            assert forbidden not in raw
        assert request.extensions['timeout']['connect'] == 2
        return httpx.Response(200, json=response())
    result = run(context, handler)
    assert result.model_calls == 1 and result.tool_calls == 0
    assert result.reason == 'clarify'


def test_read_then_prepare_tool_transcript(context):
    seen = []
    def handler(request):
        data = json.loads(request.content)
        seen.append(data)
        if len(seen) == 1:
            return httpx.Response(200, json=response([call('consultar_lista')], content='lectura'))
        transcript = data['messages']
        assert transcript[-2] == response([call('consultar_lista')], content='lectura')['message']
        assert transcript[-1]['role'] == 'tool'
        assert transcript[-1]['tool_name'] == 'consultar_lista'
        facts = json.loads(transcript[-1]['content'])
        assert facts['lines'] == [] and facts['untrusted_data'] is True
        assert sum(m['role'] == 'system' for m in transcript) == 1
        return httpx.Response(200, json=response([call('proponer_altas', {
            'items': [{'description': 'arroz'}, {'description': 'carne'}]})]))
    result = run(context, handler)
    repo, _, _ = context
    assert (result.model_calls, result.tool_calls, result.reason) == (2, 2, 'terminal')
    assert 'Pendiente, sin guardar' in result.reply.text
    assert 'Éxito inventado' not in result.reply.text
    assert repo.message_result(1)[1] == result.reply
    assert not repo.list_lines()
    assert len(repo.agent_snapshot(1, now=NOW).proposal.items) == 2


def test_terminal_result_ignores_added_model_content(context):
    requests = []
    def handler(request):
        requests.append(request)
        assert len(requests) == 1, 'terminal operation must never call model again'
        return httpx.Response(200, json=response([call('proponer_altas', {
            'items': [{'description': 'arroz', 'quantity': 2}]})]))
    result = run(context, handler)
    assert '¿Confirmas?' in result.reply.text and 'comprado' not in result.reply.text
    assert result.reply == context[0].message_result(1)[1]


def test_no_tools_cannot_send_false_success(context):
    result = run(context, lambda _: httpx.Response(200, json=response()))
    assert 'Éxito inventado' not in result.reply.text
    assert 'Aclara' in result.reply.text
    assert context[0].message_result(1)[1] is None


BAD = [
    response([call('sql')]), response([call('consultar_lista', {'extra': 1})]),
    response([{'function': {'name': 'consultar_lista', 'arguments': '{}'}}]),
    response([{'function': {'name': 'consultar_lista', 'arguments': []}}]),
    response([call('proponer_altas', {'items': [{'description': 'arroz', 'quantity': True}]})]),
    response([call('cancelar_propuesta'), call('cancelar_propuesta')]),
    response([call('cancelar_propuesta'), call('consultar_lista')]),
    response([call('consultar_lista')] * 5),
    {**response([call('cancelar_propuesta')]), 'done': False},
    {**response([call('cancelar_propuesta')]), 'done': 1},
    {**response([call('cancelar_propuesta')]), 'done_reason': 'length'},
    {**response(), 'message': {'role': 'user', 'tool_calls': [call('cancelar_propuesta')]}},
    {**response(), 'message': {'role': 'assistant', 'content': 'No', 'refusal': 'refused',
                             'tool_calls': [call('cancelar_propuesta')]}},
    {**response(), 'message': {'role': 'assistant', 'tool_calls': None}},
    {**response(), 'message': {'role': 'assistant', 'tool_calls': {}}},
]


@pytest.mark.parametrize('bad', BAD)
def test_unknown_malformed_refusal_truncated_and_redirect_fail_closed(context, bad, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('invalid model output executed a read or mutator')
    monkeypatch.setattr(context[0], 'agent_snapshot', forbidden)
    monkeypatch.setattr(context[0], 'apply_agent_operation', forbidden)
    result = run(context, lambda _: httpx.Response(200, json=bad))
    assert result.reason == 'invalid_model' and result.tool_calls == 0
    assert context[0].message_result(1)[1] is None


@pytest.mark.parametrize('kind', ['redirect', 'http', 'json', 'timeout', 'connect'])
def test_transport_failures(context, kind):
    requests = []
    def handler(request):
        requests.append(request)
        assert len(requests) == 1
        if kind == 'redirect':
            return httpx.Response(302, headers={'location': 'https://example.invalid'})
        if kind == 'http':
            return httpx.Response(500)
        if kind == 'json':
            return httpx.Response(200, content=b'{')
        if kind == 'timeout':
            raise httpx.ReadTimeout('cold load', request=request)
        raise httpx.ConnectError('offline', request=request)
    result = run(context, handler)
    assert result.reason in ('invalid_model', 'model_failure')
    assert not context[0].list_lines() and context[0].message_result(1)[1] is None


def test_non_json_numeric_constants_rejected_before_valid_mutator(context):
    encoded = json.dumps({**response([call('cancelar_propuesta')]), 'total_duration': float('nan')})
    result = run(context, lambda _: httpx.Response(200, content=encoded.encode()))
    assert result.reason == 'invalid_model' and result.tool_calls == 0
    assert context[0].message_result(1)[1] is None


def test_entire_batch_validated_before_reads(context, monkeypatch):
    monkeypatch.setattr(context[0], 'find_products', lambda *_: pytest.fail('read before validation'))
    result = run(context, lambda _: httpx.Response(200, json=response([
        call('consultar_ficha', {'query': 'arroz'}), call('sql')])))
    assert result.tool_calls == 0


@pytest.mark.parametrize('batch_size,expected_models,expected_tools', [(1, 4, 4), (4, 2, 8)])
def test_limit_and_readonly_results(context, batch_size, expected_models, expected_tools):
    result = run(context, lambda _: httpx.Response(200, json=response([call('consultar_lista')] * batch_size)))
    assert (result.model_calls, result.tool_calls) == (expected_models, expected_tools)
    assert result.reason == 'limit'
    assert 'La lista está vacía' in result.reply.text and 'Éxito inventado' not in result.reply.text
    assert context[0].message_result(1)[1] is None


def test_tool_budget_rejects_whole_overflow_batch(context):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=response([call('consultar_lista')] * (3 if len(seen) < 3 else 4)))
    result = run(context, handler)
    assert (result.model_calls, result.tool_calls, result.reason) == (3, 6, 'limit')


@pytest.mark.parametrize('ending,reason', [('prose', 'readonly'), ('invalid', 'invalid_model'),
                                          ('offline', 'model_failure')])
def test_read_facts_survive_later_failure_or_model_prose(context, ending, reason):
    seen = []
    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(200, json=response([call('consultar_lista')]))
        if ending == 'invalid':
            return httpx.Response(200, content=b'{')
        if ending == 'offline':
            raise httpx.ConnectError('offline', request=request)
        return httpx.Response(200, json=response(content='La lista contiene diez productos'))
    result = run(context, handler)
    assert result.reason == reason
    assert 'La lista está vacía' in result.reply.text and 'diez productos' not in result.reply.text


def test_limit_and_cancellation(context):
    def handler(_):
        raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        run(context, handler)
    assert context[0].message_result(1)[1] is None


def test_global_timeout_covers_whole_loop(context, monkeypatch):
    from shopping_agent import ollama
    real_timeout = asyncio.timeout
    monkeypatch.setattr(ollama, 'RUN_TIMEOUT', 0.02)
    entered = []
    def timeout(seconds):
        entered.append(seconds)
        return real_timeout(seconds)
    monkeypatch.setattr(ollama.asyncio, 'timeout', timeout)
    async def handler(_):
        await asyncio.sleep(0.1)
        return httpx.Response(200, json=response())
    result = run(context, handler)
    assert entered == [0.02] and result.reason == 'model_failure'


def test_schema_does_not_depend_on_source_phrase(context):
    repo, _, _ = context
    definitions = []
    for update, text in enumerate(('hola', 'añade arroz', 'qué lista tengo', 'frase nueva'), 2):
        message = IncomingMessage(update_id=update, user_id=7, chat_id=7, text=text)
        repo.ingest_batch([message], update + 1)
        def handler(request):
            definitions.append(json.loads(request.content)['tools'])
            return httpx.Response(200, json=response())
        run((repo, message, AgentTools(repo, message, now=NOW)), handler)
    assert all(d == definitions[0] for d in definitions) and len(definitions[0]) == 7


def test_initial_payload_overflow_fails_before_any_http(context):
    repo, _, _ = context
    message = IncomingMessage(update_id=2, user_id=7, chat_id=7, text='ñ' * 24000)
    repo.ingest_batch([message], 3)
    result = run((repo, message, AgentTools(repo, message, now=NOW)),
                 lambda _: pytest.fail('overflow made HTTP request'))
    assert result.reason == 'context_overflow' and result.model_calls == 0
    assert repo.message_result(2)[1] is None


def test_overflow_after_successful_read_preserves_facts(context):
    repo, _, _ = context
    title = 'arroz observado'
    with repo._connection(write=True) as db:
        db.execute('INSERT INTO observed_products VALUES (?,?,?,?,?,?,?,?,?)',
                   ('big', 'fuente', 'rice', title, 'https://example.invalid', '2026-01-01', 123, 1, 'formato'))
    requests = []
    def handler(request):
        requests.append(request)
        assert len(requests) == 1, 'overflow transcript reached network'
        return httpx.Response(200, json=response([call('consultar_ficha', {'query': 'arroz'})],
                                               content='ñ' * 15000))
    result = run(context, handler)
    assert (result.reason, result.model_calls, result.tool_calls) == ('context_overflow', 1, 1)
    assert title in result.reply.text and 'precio observado 1,23' in result.reply.text
    assert repo.message_result(1)[1] is None


def test_full_read_context_overflow_preserves_operational_reply_and_snapshot(context):
    repo, _, _ = context
    message = IncomingMessage(update_id=2, user_id=7, chat_id=7, text='x' * 4300)
    repo.ingest_batch([message], 3)
    tools = AgentTools(repo, message, now=NOW)
    before = tools.snapshot
    requests = []
    def handler(request):
        requests.append(request)
        assert len(requests) == 1, 'complete tool context overflow reached network'
        data = json.loads(request.content)
        assert len(json.dumps({'messages': data['messages'], 'tools': data['tools']},
                              ensure_ascii=False, separators=(',', ':')).encode()) <= 24000
        return httpx.Response(200, json=response([call('consultar_lista')], content=''))
    result = run((repo, message, tools), handler)
    assert (result.reason, result.model_calls, result.tool_calls) == ('context_overflow', 1, 1)
    assert 'La lista está vacía' in result.reply.text
    assert tools.snapshot == before and repo.message_result(2)[1] is None


def test_review_permissions_never_enter_initial_or_tool_context(context):
    from shopping_agent.contracts import ToolCall
    repo, _, tools = context
    prepared = tools.validate_calls((ToolCall(name='proponer_altas', arguments={
        'items': [{'description': 'arroz', 'quantity': 2}]}),))
    tools.execute(prepared[0])
    message = IncomingMessage(update_id=2, user_id=7, chat_id=7, text='consulta propuesta')
    repo.ingest_batch([message], 3)
    tools = AgentTools(repo, message, now=NOW)
    assert tools.snapshot.proposal.reviewed_revision == 1
    seen = []
    def handler(request):
        raw = request.content.decode()
        for forbidden in ('reviewed_revision', 'reviewed_update_id', 'user_id', 'chat_id'):
            assert forbidden not in raw
        seen.append(json.loads(raw))
        if len(seen) == 1:
            return httpx.Response(200, json=response([call('consultar_propuesta')]))
        facts = json.loads(seen[-1]['messages'][-1]['content'])
        assert facts['proposal']['items'][0]['quantity'] == 2
        return httpx.Response(200, json=response())
    result = run((repo, message, tools), handler)
    assert result.reason == 'readonly' and '¿Confirmas?' in result.reply.text
    assert repo.agent_snapshot(2, now=NOW).proposal.reviewed_revision == 1


def test_cancellation_after_committed_operation_is_recoverable(context, monkeypatch):
    tools = context[2]
    execute = tools.execute
    def commit_then_cancel(call):
        execute(call)
        raise asyncio.CancelledError
    monkeypatch.setattr(tools, 'execute', commit_then_cancel)
    with pytest.raises(asyncio.CancelledError):
        run(context, lambda _: httpx.Response(200, json=response([call('proponer_altas', {
            'items': [{'description': 'arroz', 'quantity': 2}]})])))
    reply = context[0].message_result(1)[1]
    assert reply is not None and 'Pendiente, sin guardar' in reply.text
    assert context[0].agent_snapshot(1, now=NOW).proposal.items[0].quantity == 2
    assert not context[0].list_lines()


def test_storage_errors_are_not_concealed_as_model_failures(context, monkeypatch):
    def broken(*args, **kwargs):
        raise sqlite3.OperationalError('storage broken')
    monkeypatch.setattr(context[0], 'apply_agent_operation', broken)
    with pytest.raises(sqlite3.OperationalError, match='storage broken'):
        run(context, lambda _: httpx.Response(200, json=response([call('cancelar_propuesta')])))


def test_message_binding_rejects_changed_text_before_network(context):
    repo, message, tools = context
    forged = message.model_copy(update={'text': 'otro texto'})
    with pytest.raises(ValueError):
        run((repo, forged, tools), lambda _: pytest.fail('forged context reached network'))
