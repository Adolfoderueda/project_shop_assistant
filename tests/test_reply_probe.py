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
    # Audit reads as well as checking unchanged bytes; subprocess must never load settings.
    hook = tmp_path / "sitecustomize.py"
    hook.write_text(
        "import sys\n"
        f"sentinel = {str(sentinel)!r}\n"
        "def guard(event, args):\n"
        "    if event == 'open' and str(args[0]) == sentinel:\n"
        "        raise RuntimeError('private sentinel read')\n"
        "sys.addaudithook(guard)\n" + hook_code, encoding="utf-8")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-File", str(ROOT / "scripts/Probe-Replies.ps1"),
         "-Python", sys.executable, *flags], cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(tmp_path)}, timeout=120, check=False)
    assert sentinel.read_bytes() == b"PRIVATE SENTINEL DO NOT READ"
    records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    return result, records


@pytest.mark.parametrize("mode", ["-Offline", "-OfflineReject"])
def test_probe_offline_pass_and_rejection_fallback(tmp_path, mode):
    result, records = run_probe(tmp_path, mode)
    assert result.returncode == 0, result.stdout + result.stderr
    cases = [r for r in records if "case" in r]
    assert len(cases) == 20
    assert all(r["passed"] and r["orders"] == 0 for r in cases)
    assert all(all(r["checks"].values()) for r in cases)
    assert records[-1]["status"] == "PASS"
    assert records[-1]["accepted"] == (18 if mode == "-Offline" else 0)
    assert records[-1]["fallback"] == (2 if mode == "-Offline" else 20)
    added = next(r for r in cases if r["case"] == "add_known")
    assert added["input"] == "añade 2 arroz"
    assert added["rows"] == [["arroz", 2]]
    assert added["snapshot"]["kind"] == "added"
    assert added["interpreter_calls"] == 0  # Existing no-slash alias, not model quantity.
    assert added["accepted"] is (mode == "-Offline")
    assert not Path(records[0]["temporary_root"]).exists()
    assert records[-1]["temporary_removed"] is True


def test_probe_failed_expectation_exit_one(tmp_path):
    result, records = run_probe(tmp_path, "-Offline", "-FailExpectation")
    assert result.returncode == 1, result.stdout + result.stderr
    assert len([r for r in records if "case" in r]) == 20
    assert records[-1]["status"] == "FAIL"
    assert {"duplicate_rice:rows", "add_known:question"} <= set(records[-1]["failures"])
    assert "duplicate_rice:quality" in records[-1]["failures"]
    assert next(r for r in records if r.get("case") == "duplicate_rice")["accepted"] is False
    assert records[-1]["temporary_removed"] is True
    assert not Path(records[0]["temporary_root"]).exists()


def test_probe_scenario_exception_reports_unknown_orders_and_cleans_up(tmp_path):
    # Inject only one offline conversation failure; execute the real probe catch/finally.
    hook_code = (
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from conversation import Conversation\n"
        "original_handle = Conversation.handle\n"
        "async def failing_handle(self, message, mode):\n"
        "    if self.repo.path.name == 'duplicate_rice.db' and self.reply_writer is not None:\n"
        "        raise RuntimeError('invented scenario failure before order measurement')\n"
        "    return await original_handle(self, message, mode)\n"
        "Conversation.handle = failing_handle\n"
        "import httpx\n"
        "async def forbid_http(self, request):\n"
        "    raise RuntimeError('offline fixture forbids HTTP')\n"
        "httpx.AsyncHTTPTransport.handle_async_request = forbid_http\n"
    )
    result, records = run_probe(tmp_path, "-Offline", hook_code=hook_code)
    assert result.returncode == 1, result.stdout + result.stderr
    cases = [r for r in records if "case" in r]
    assert len(cases) == 20, result.stdout + result.stderr
    failed = next(r for r in cases if r["case"] == "duplicate_rice")
    assert failed["passed"] is False
    assert failed["error"] == "RuntimeError"
    assert failed["detail"] == "invented scenario failure before order measurement"
    assert failed["orders"] is None
    assert all(r["passed"] and r["orders"] == 0 for r in cases if r is not failed)
    assert records[-1]["status"] == "FAIL"
    assert records[-1]["failures"] == ["duplicate_rice:exception"]
    assert records[-1]["temporary_removed"] is True
    assert not Path(records[0]["temporary_root"]).exists()


def test_unavailable_service_exit_two(tmp_path):
    result, records = run_probe(tmp_path, "-TestUnavailable")
    assert result.returncode == 2, result.stdout + result.stderr
    assert records[-1]["status"] == "PENDING"
    assert records[-1]["temporary_removed"] is True
    assert not Path(records[0]["temporary_root"]).exists()
