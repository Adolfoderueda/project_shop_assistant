"""Execute the opt-in script, including real provider codecs with injected HTTP."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_probe(tmp_path, *flags, hook_code=""):
    sentinel = tmp_path / "private" / "settings.json"
    sentinel.parent.mkdir()
    sentinel.write_bytes(b"PRIVATE SENTINEL DO NOT READ")
    audit = tmp_path / "reads.txt"
    (tmp_path / "sitecustomize.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "def guard(event, args):\n"
        f"    if event == 'open' and str(args[0]) == {str(sentinel)!r}:\n"
        f"        with open({str(audit)!r}, 'w') as log: log.write('READ')\n"
        "        raise RuntimeError('private sentinel read')\n"
        "sys.addaudithook(guard)\n" + hook_code, encoding="utf-8")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-File", str(ROOT / "scripts/Probe-NaturalDialogue.ps1"),
         "-Python", sys.executable, *flags], cwd=tmp_path, capture_output=True,
        text=True, env={**os.environ, "PYTHONPATH": str(tmp_path)}, timeout=180, check=False)
    assert not audit.exists()
    assert sentinel.read_bytes() == b"PRIVATE SENTINEL DO NOT READ"
    records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    return result, records


# Simulated HTTP only: real mode still constructs/executes both Ollama providers.
LOCAL_HTTP = """
import httpx, json
async def local_http(self, request):
    if request.url.path in ('/api/tags', '/api/ps'):
        return httpx.Response(200, json={'models':[{'name':'gemma4:e2b'}]})
    data = json.loads(request.content)
    context = json.loads(data['messages'][1]['content'])
    if 'text' in context:
        branch = data['format']['anyOf'][0]['properties']
        action = branch['action']['enum'][0]
        lines = []
        if branch['lines']['maxItems']:
            name = branch['lines']['items']['properties']['description']['enum'][0]
            lines = [{'description':name, 'quantity':None}]
        content = {'action':action, 'lines':lines}
    else:
        items = data['format']['properties']['blocks']['anyOf'][0]['prefixItems']
        content = {'blocks':[{'role':b['properties']['role']['const'],
                             'text':b['properties']['text']['enum'][0]} for b in items]}
    return httpx.Response(200, json={'done':True, 'done_reason':'stop',
        'message':{'role':'assistant', 'content':json.dumps(content)}})
httpx.AsyncHTTPTransport.handle_async_request = local_http
"""


def test_real_mode_does_not_substitute_interpreter(tmp_path):
    result, records = run_probe(tmp_path, hook_code=LOCAL_HTTP)
    assert result.returncode == 0, result.stdout + result.stderr
    steps = [r for r in records if "step" in r]
    assert records[-1]["mode"] == "REAL"
    for action in ("add", "increment", "list"):
        calls = [r for r in steps if r.get("required_intent") == action]
        assert calls and all(r["proposal"]["action"] == action for r in calls)
        assert all(r["interpreter_calls"] == 1 and r["writer_accepted"] for r in calls)
        for record in calls:
            context = next(e["context"] for e in record["requests"] if e["provider"] == "interpreter")
            assert all("id" not in line and "revision" not in line for line in context["lines"])
            assert "user_id" not in context and "confirmed" not in context
    assert all(r["passed"] for r in steps)
    assert records[-1]["coverage"] == ["add", "increment", "list"]
    assert any(r.get("replay") and r["interpreter_calls"] == r["writer_calls"] == 0 for r in steps)
    replay = next(r for r in steps if r["replay"])
    original = next(r for r in steps if r["case"] == "C" and r["step"] == 8 and not r["replay"])
    assert replay["now"] > original["now"]
    assert replay["state"] == original["state"] and replay["reply"] == original["reply"]
    assert [r["input"] for r in steps if r["case"] == "A"] == [
        "hols", "hola que tal", "quiero mas arroz", "cancelar", "dame mi lista"]
    b = [r for r in steps if r["case"] == "B"]
    assert all(not any(row[0] == "avena" for row in r["rows"]) for r in b[:5])
    assert all(r["rows"][-1] == ["avena", 2] for r in b[5:])
    assert b[0]["state"]["expires_at"] == b[1]["state"]["expires_at"] == b[2]["state"]["expires_at"]
    c = [r for r in steps if r["case"] == "C" and not r["replay"]]
    assert all(r["rows"][0] == ["arroz", 1] for r in c[:7])
    assert all(r["rows"][0] == ["arroz", 3] for r in c[7:])
    assert c[2]["state"]["base_quantity"] == 1
    assert c[2]["state"]["additional_quantity"] == 2
    assert c[2]["state"]["proposal_quantity"] == 3
    assert {r["snapshot"]["act"] for r in steps if r["snapshot"]} >= {
        "greeting", "pending_add", "select_entry", "increment_amount", "increment_confirm", "result", "list"}
    assert not Path(records[0]["temporary_root"]).exists()


@pytest.mark.parametrize("flags,code,status", [
    (["-Offline"], 0, "PASS"),
    (["-Offline", "-FailExpectation"], 1, "FAIL"),
    (["-TestUnavailable"], 2, "PENDING"),
])
def test_offline_exit_cleanup_and_unknown_error_metrics(tmp_path, flags, code, status):
    result, records = run_probe(tmp_path, *flags)
    assert result.returncode == code, result.stdout + result.stderr
    assert records[-1]["status"] == status
    assert records[-1]["temporary_removed"] is True
    assert not Path(records[0]["temporary_root"]).exists()


def test_exception_orders_are_unknown(tmp_path):
    hook = """
from conversation import Conversation
original = Conversation.handle
async def failing(self, message, mode):
    if self.repo.path.name == 'A.db' and message.update_id == 1:
        raise RuntimeError('synthetic boundary failure')
    return await original(self, message, mode)
Conversation.handle = failing
"""
    result, records = run_probe(tmp_path, "-Offline", hook_code=hook)
    assert result.returncode == 1, result.stdout + result.stderr
    failed = next(r for r in records if r.get("error"))
    assert failed["orders"] is None and not failed["passed"]
    assert records[-1]["temporary_removed"]


def test_quality_cannot_pass_fallback_only(tmp_path):
    hook = LOCAL_HTTP.replace("'content':json.dumps(content)",
                        "'content':json.dumps(content if 'text' in context else "
                        "{'blocks':[{'role':'fact','text':'Comprado todo'}]})")
    result, records = run_probe(tmp_path, hook_code=hook)
    assert result.returncode == 1, result.stdout + result.stderr
    assert records[-1]["status"] == "FAIL"
    assert records[-1]["coverage"] == []
    assert any("quality" in failure for failure in records[-1]["failures"])


def test_real_untrusted_intent_cannot_gain_purchase_authority(tmp_path):
    hook = LOCAL_HTTP.replace("content = {'action':action, 'lines':lines}",
                              "content = {'action':'buy', 'lines':[]}")
    result, records = run_probe(tmp_path, hook_code=hook)
    assert result.returncode == 1, result.stdout + result.stderr
    steps = [r for r in records if "step" in r]
    assert all(r["orders"] == 0 for r in steps)
    assert all(r["rows"] == [["arroz", 1], ["ARROZ", 2], ["arroz integral", None]]
               for r in steps if r["case"] in {"A", "B"})
    # Source grammar independently authorizes an increment proposal; only the later
    # explicit selection/delta/yes authorizes its save, never the injected buy.
    assert all(r["rows"] == r["expected_rows"] for r in steps if r["case"] == "C")
