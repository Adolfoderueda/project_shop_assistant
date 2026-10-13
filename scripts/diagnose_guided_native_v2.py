"""Version 2: isolate omitted existing skills, not new prompt recipes."""

import asyncio
import base64
import hashlib
import json
from pathlib import Path

import httpx

from shopping_agent.contracts import AgentSnapshot
from shopping_agent.guided_contracts import GuidedState
from shopping_agent.guided_ollama import GuidedOllamaAgent
from shopping_agent.ollama import _assistant, _json
from shopping_agent.skills import load_skills
from tests.guided_helpers import message

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/superpowers/evidence/2026-10-09-preguntas-guiadas/native-diagnosis-v2.jsonl'
INPUTS = ('huevos, carne y atun', 'leche dos', 'atun dos, huevos uno y carne')


async def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    requests = []
    for text in INPUTS:
        event = message(1, text)
        snapshot = AgentSnapshot(user_id=7, chat_id=7, source_update_id=1, original_text=text)
        captured = []

        def capture(request, captured=captured):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={'done': True, 'done_reason': 'stop',
                'message': {'role': 'assistant', 'content': ''}})

        await GuidedOllamaAgent(transport=httpx.MockTransport(capture)).interpret(
            event, GuidedState(snapshot=snapshot), ())
        baseline = captured.pop()
        skills = json.loads(_json(baseline))
        skills['messages'][0]['content'] += '\n\n' + load_skills()
        for arm, request in (('guided-baseline', baseline), ('guided-existing-skills', skills)):
            requests.append((text, arm, _json(request).encode()))
    with OUT.open('x', encoding='utf-8', newline='\n') as output:
        output.write(_json({'type': 'manifest', 'version': 2,
            'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'inputs': INPUTS, 'arms': ['guided-baseline', 'guided-existing-skills'],
            'hypothesis': 'The guided runner omits existing skill procedures used by the original agent; append those unchanged skills only. Tool schemas, user/context and resources remain identical.',
            'native_only': True, 'calls_per_input_arm': 1}) + '\n')
        async with httpx.AsyncClient(base_url='http://127.0.0.1:11434', trust_env=False,
                                     follow_redirects=False, timeout=120) as client:
            tags = await client.get('/api/tags')
            tags.raise_for_status()
            output.write(_json({'type': 'tags', 'response': tags.text,
                'response_base64': base64.b64encode(tags.content).decode()}) + '\n')
            output.flush()
            for text, arm, request in requests:
                response = await client.post('/api/chat', content=request,
                                             headers={'Content-Type': 'application/json'})
                record = {'type': 'call', 'input': text, 'arm': arm, 'status': response.status_code,
                    'request': request.decode(), 'request_base64': base64.b64encode(request).decode(),
                    'request_sha256': hashlib.sha256(request).hexdigest(),
                    'response': response.text, 'response_base64': base64.b64encode(response.content).decode(),
                    'response_sha256': hashlib.sha256(response.content).hexdigest()}
                try:
                    _, calls = _assistant(response.json())
                    record['native_tools'] = [c.model_dump(mode='json') for c in calls]
                except ValueError as exc:
                    record['envelope_error'] = str(exc)
                output.write(_json(record) + '\n')
                output.flush()
                print(text, arm, record.get('native_tools', record.get('envelope_error')))


if __name__ == '__main__':
    asyncio.run(main())
