import asyncio
import json

import httpx

from shopping_agent.contracts import AgentSnapshot
from shopping_agent.guided_contracts import GuidedState
from shopping_agent.guided_ollama import SYSTEM, GuidedOllamaAgent
from shopping_agent.skills import load_skills
from tests.guided_helpers import message


def test_runner_reuses_existing_skill_procedures_without_schema_or_resource_change():
    captured = []

    def respond(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {
            'role': 'assistant', 'tool_calls': [{'function': {'name': 'proponer_altas',
                'arguments': {'items': [{'description': 'leche'}]}}}]}})

    event = message(1, 'leche')
    state = GuidedState(snapshot=AgentSnapshot(user_id=7, chat_id=7, source_update_id=1, original_text='leche'))
    result = asyncio.run(GuidedOllamaAgent(transport=httpx.MockTransport(respond)).interpret(event, state, ()))
    assert result.reason == 'candidate'
    request, = captured
    assert request['messages'][0]['content'] == SYSTEM + '\n\n' + load_skills()
    assert request['options'] == {'temperature': 0, 'num_ctx': 8192, 'num_predict': 512}
    assert request['think'] is False
    assert len(json.dumps({k: request[k] for k in ('messages', 'tools')},
                          ensure_ascii=False, separators=(',', ':')).encode()) <= 24000
