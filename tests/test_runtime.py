"""Offline runtime safety and lifecycle contracts."""

import asyncio
import json
import logging
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from config import Settings, load_settings
from runtime import ProcessLock, run


def settings(tmp_path):
    return Settings(telegram_token="secret-token", authorized_user_id=123,
                    address="private destination", database_path=tmp_path / "assistant.db",
                    logs_path=tmp_path / "private" / "logs",
                    profiles_path=tmp_path / "private" / "profiles")


def test_missing_configuration_has_actionable_message(tmp_path):
    with pytest.raises(ValueError, match="configure"):
        load_settings(tmp_path)


def test_legacy_openai_settings_select_openai_without_rewriting_file(tmp_path):
    from config import save_settings

    old = Settings(telegram_token="secret-token", authorized_user_id=123,
                   address="private destination", database_path=tmp_path / "private" /
                   "assistant.db", openai_model="legacy", openai_api_key="key")
    save_settings(tmp_path, old)
    target = tmp_path / "private" / "settings.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload.pop("model_provider", None)
    target.write_text(json.dumps(payload), encoding="utf-8")
    before = target.read_bytes()
    assert load_settings(tmp_path).model_provider == "openai"
    assert target.read_bytes() == before


def test_model_local_enable_disable_preserves_private_state(tmp_path, monkeypatch, capsys):
    import cli
    from config import save_settings
    from domain import IncomingMessage, Intent, IntentLine
    from storage import Repository

    original = settings(tmp_path).model_copy(update={"database_path": tmp_path / "private" /
                                             "assistant.db", "telegram_bot_id": 777})
    save_settings(tmp_path, original)
    repo = Repository(original.database_path)
    repo.migrate()
    repo.ingest_batch([IncomingMessage(update_id=3, user_id=123, chat_id=123,
                                       text="/anadir 1 pienso")], 4)
    repo.apply_intent(3, Intent(action="add", lines=[IntentLine(description="pienso", quantity=1)]),
                      "dry_run")
    repo.ingest_batch([IncomingMessage(update_id=4, user_id=123, chat_id=123,
                                       text="/comprar")], 5)
    repo.apply_intent(4, Intent(action="buy"), "dry_run")
    before = (repo.list_lines(), repo.pending_orders(), repo.telegram_offset())

    async def available(_): return True
    monkeypatch.setattr(cli, "ollama_available", available)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["model-local", "enable"]) == 0
    enabled = load_settings(tmp_path)
    assert enabled.model_provider == "ollama"
    assert enabled.ollama_model == "gemma4:e2b"
    assert enabled.telegram_token.get_secret_value() == "secret-token"
    assert enabled.telegram_bot_id == 777
    assert enabled.authorized_user_id == 123
    assert (repo.list_lines(), repo.pending_orders(), repo.telegram_offset()) == before
    assert cli.main(["model-local", "status"]) == 0
    assert "ollama" in capsys.readouterr().out
    assert cli.main(["model-local", "disable"]) == 0
    assert load_settings(tmp_path).model_provider == "commands_only"
    assert (repo.list_lines(), repo.pending_orders(), repo.telegram_offset()) == before


def test_model_local_enable_failure_and_busy_lock_never_rewrite_settings(tmp_path, monkeypatch, capsys):
    import cli
    from config import save_settings

    original = settings(tmp_path).model_copy(update={"database_path": tmp_path / "private" /
                                             "assistant.db"})
    save_settings(tmp_path, original)
    target = tmp_path / "private" / "settings.json"
    before = target.read_bytes()
    monkeypatch.chdir(tmp_path)

    async def unavailable(_): return False
    monkeypatch.setattr(cli, "ollama_available", unavailable)
    assert cli.main(["model-local", "enable"]) == 1
    assert target.read_bytes() == before
    with ProcessLock(tmp_path / "private" / "worker.lock"):
        assert cli.main(["model-local", "disable"]) == 1
    output = capsys.readouterr().out.lower()
    assert "worker" in output and "stop" in output
    assert "secret-token" not in output
    assert target.read_bytes() == before


def test_model_local_cannot_change_nested_database_settings_while_runtime_holds_lock(
        tmp_path, monkeypatch):
    import cli
    from config import save_settings

    nested = tmp_path / "private" / "nested" / "assistant.db"
    save_settings(tmp_path, settings(tmp_path).model_copy(update={"database_path": nested}))
    target = tmp_path / "private" / "settings.json"
    before = target.read_bytes()
    monkeypatch.chdir(tmp_path)

    class Repo:
        def migrate(self): pass
        def assert_authorized_owner(self, uid): assert uid == 123
        def pending_messages(self): return []
        def resumable_orders(self): return []
        def pending_orders(self): return []

    class Recovery:
        async def recover(self): pass

    class Checkout:
        async def run(self, order_id): pytest.fail("unexpected checkout")

    class IO:
        async def send_pending(self): pass
        async def poll_once(self):
            assert await cli.model_local(tmp_path, "disable") is False
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(load_settings(tmp_path), repo=Repo(), recovery=Recovery(),
                        checkout=Checkout(), transport=IO()))
    assert target.read_bytes() == before


def test_model_local_rejects_database_path_changed_before_lock_acquisition(tmp_path,
                                                                           monkeypatch):
    import cli
    import runtime
    from config import save_settings

    first = settings(tmp_path).model_copy(update={"database_path": tmp_path / "private" /
                                          "first" / "assistant.db"})
    save_settings(tmp_path, first)
    target = tmp_path / "private" / "settings.json"
    second = first.model_copy(update={"database_path": tmp_path / "private" /
                                      "second" / "assistant.db", "model_provider": "ollama"})
    actual_lock = runtime.ProcessLock

    class ChangeBeforeLock(actual_lock):
        def __enter__(self):
            save_settings(tmp_path, second)
            return super().__enter__()

    monkeypatch.setattr(runtime, "ProcessLock", ChangeBeforeLock)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["model-local", "disable"]) == 1
    assert load_settings(tmp_path).database_path == second.database_path.resolve()
    assert load_settings(tmp_path).model_provider == "ollama"
    assert target.is_file()


@pytest.mark.parametrize("response", [
    (200, {"models": [{"name": "gemma4:12b"}]}),
    (200, {"models": "malformed"}),
    (302, {"models": [{"name": "gemma4:e2b"}]}),
])
def test_model_diagnostic_rejects_missing_model_unexpected_response_and_redirect(response):
    import httpx

    from cli import ollama_available

    status, data = response
    transport = httpx.MockTransport(lambda _: httpx.Response(status, json=data,
                                                               headers={"location": "http://evil/"}))
    assert asyncio.run(ollama_available("gemma4:e2b", transport=transport)) is False


def test_model_diagnostic_never_uses_proxy_and_closes_http_client(monkeypatch):
    import httpx

    import cli

    clients = []
    real = httpx.AsyncClient

    def client(**kwargs):
        clients.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(cli, "httpx", SimpleNamespace(AsyncClient=client, Timeout=httpx.Timeout))
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, json={"models": [{"name": "gemma4:e2b"}]}))
    assert asyncio.run(cli.ollama_available("gemma4:e2b", transport=transport)) is True
    assert clients[0]["trust_env"] is False
    assert clients[0]["follow_redirects"] is False
    assert clients[0]["base_url"] == "http://127.0.0.1:11434"


def test_runtime_ollama_failure_keeps_commands_working_without_openai_fallback(tmp_path,
                                                                                monkeypatch):
    import httpx

    import ollama_interpreter
    from domain import IncomingMessage
    from storage import Repository

    repo = Repository(tmp_path / "assistant.db")
    repo.migrate()
    repo.ingest_batch([
        IncomingMessage(update_id=1, user_id=123, chat_id=123, text="necesito pienso"),
        IncomingMessage(update_id=2, user_id=123, chat_id=123, text="/lista"),
    ], 3)
    configured = settings(tmp_path).model_copy(update={"model_provider": "ollama",
                                                 "openai_api_key": "unused-key",
                                                 "openai_model": "old"})
    clients = []
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda _: httpx.Response(503))

    def client(**kwargs):
        result = real_client(**{**kwargs, "transport": transport})
        clients.append(result)
        return result

    # A local server fault must not trigger a remote provider or stop subsequent commands.
    monkeypatch.setattr(ollama_interpreter, "httpx", SimpleNamespace(AsyncClient=client,
                                                                    Timeout=httpx.Timeout))

    class Recovery:
        async def recover(self): pass

    class Checkout:
        async def run(self, order_id): pytest.fail("unexpected checkout")

    class IO:
        async def send_pending(self): pass
        async def poll_once(self): raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(configured, repo=repo, recovery=Recovery(), checkout=Checkout(),
                        transport=IO()))
    assert len(repo.pending_notices()) == 2
    assert repo.telegram_offset() == 3
    assert len(clients) == 1 and clients[0].is_closed


def test_runtime_closes_legacy_openai_client_on_shutdown(tmp_path, monkeypatch):
    import openai

    clients = []

    class Client:
        def __init__(self, *, api_key):
            assert api_key == "legacy-key"
            self.closed = False
            clients.append(self)

        async def close(self): self.closed = True

    monkeypatch.setattr(openai, "AsyncOpenAI", Client)
    configured = Settings(telegram_token="secret-token", authorized_user_id=123,
                          address="private destination", database_path=tmp_path / "assistant.db",
                          openai_model="legacy", openai_api_key="legacy-key")

    class Repo:
        def migrate(self): pass
        def assert_authorized_owner(self, uid): assert uid == 123
        def pending_messages(self): return []
        def resumable_orders(self): return []
        def pending_orders(self): return []

    class Recovery:
        async def recover(self): pass

    class Checkout:
        async def run(self, order_id): pytest.fail("unexpected checkout")

    class IO:
        async def send_pending(self): pass
        async def poll_once(self): raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(configured, repo=Repo(), recovery=Recovery(), checkout=Checkout(),
                        transport=IO()))
    assert len(clients) == 1 and clients[0].closed


def test_second_process_cannot_start(tmp_path):
    with (ProcessLock(tmp_path / "worker.lock"),
          pytest.raises(RuntimeError, match="already running"),
          ProcessLock(tmp_path / "worker.lock")):
        pytest.fail("second worker entered")
    with ProcessLock(tmp_path / "worker.lock"):
        pass


def test_separate_process_does_not_enter_worker(tmp_path):
    lock = tmp_path / "worker.lock"
    code = ("from runtime import ProcessLock\n"
            "import sys\n"
            "try:\n"
            "    with ProcessLock(sys.argv[1]):\n"
            "        sys.exit(99)\n"
            "except RuntimeError:\n"
            "    sys.exit(42)\n")
    with ProcessLock(lock):
        result = subprocess.run([sys.executable, "-c", code, str(lock)],
                                capture_output=True, timeout=10, check=False)
    assert result.returncode == 42


def test_restart_recovers_before_new_checkout(tmp_path):
    events = []

    class Repo:
        def migrate(self): events.append("migrate")
        def assert_authorized_owner(self, uid): events.append("owner_checked")
        def pending_messages(self): return []
        def pending_orders(self): return ["new"]
        def resumable_orders(self): return []

    class Recovery:
        async def recover(self): events.append("recover")

    class Checkout:
        async def run(self, order_id): events.append("checkout:" + order_id)

    class IO:
        async def poll_once(self): events.append("poll")
        async def send_pending(self): events.append("outbox")

    async def stop_after_cycle(_):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(settings(tmp_path), repo=Repo(), recovery=Recovery(),
                        checkout=Checkout(), transport=IO(), sleep=stop_after_cycle))
    assert events.index("recover") < events.index("checkout:new")
    assert events.index("recover") < events.index("poll")


def test_shutdown_preserves_pending_work(tmp_path):
    from domain import IncomingMessage
    from storage import Repository

    repo = Repository(tmp_path / "assistant.db")
    repo.migrate()
    msg = IncomingMessage(update_id=1, user_id=123, chat_id=123, text="/lista")
    repo.ingest_batch([msg], 2)

    class Recovery:
        async def recover(self): pass

    class IO:
        async def poll_once(self): pass
        async def send_pending(self): pass

    class Conversation:
        async def handle(self, message, mode): raise asyncio.CancelledError

    class Checkout:
        async def run(self, order_id): pass

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(settings(tmp_path), repo=repo, recovery=Recovery(), transport=IO(),
                        conversation=Conversation(), checkout=Checkout()))
    assert repo.pending_messages() == [msg]


def test_logs_redact_secrets(tmp_path, caplog):
    from runtime import configure_logging
    settings_ = settings(tmp_path)
    configure_logging(settings_)
    with caplog.at_level(logging.INFO, logger="runtime"):
        logging.getLogger("runtime").info("Worker started")
    log = (tmp_path / "private" / "logs" / "worker.log").read_text(encoding="utf-8")
    assert "Worker started" in log
    assert "secret-token" not in log
    assert "private destination" not in log
    assert "secret-token" not in caplog.text
    assert "private destination" not in caplog.text


def test_configuration_private_and_default_dry_run(tmp_path):
    from config import save_settings

    save_settings(tmp_path, settings(tmp_path).model_copy(update={"database_path":
                                                              tmp_path / "private" / "assistant.db"}))
    loaded = load_settings(tmp_path)
    assert loaded.mode == "dry_run"
    assert loaded.authorized_user_id == 123
    assert loaded.database_path == (tmp_path / "private" / "assistant.db").resolve()
    assert "secret-token" not in repr(loaded)


def test_binding_ignores_old_and_foreign_chats():
    from types import SimpleNamespace

    from cli import bind_user

    def update(id, uid, chat, text):
        user = SimpleNamespace(id=uid, is_bot=False)
        message = SimpleNamespace(text=text, from_user=user,
                                  chat=SimpleNamespace(id=chat, type="private"),
                                  forward_origin=None, via_bot=None, sender_chat=None,
                                  sender_business_bot=None, quote=None,
                                  is_automatic_forward=False)
        return SimpleNamespace(update_id=id, message=message)

    class Bot:
        def __init__(self): self.offsets = []
        async def get_updates(self, *, offset=None, **_):
            self.offsets.append(offset)
            if offset is None:
                return [update(5, 123, 123, "/start nonce")]
            return [update(6, 123, 999, "/start nonce"),
                    update(7, 123, 123, "/start nonce")]

    bot = Bot()
    assert asyncio.run(bind_user(bot, "nonce")) == (123, 8)
    assert bot.offsets == [None, 6]


def test_reconfigure_preserves_offline_pending_offset(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import cli
    from config import save_settings
    from storage import Repository

    existing = settings(tmp_path).model_copy(update={
        "database_path": tmp_path / "private" / "assistant.db", "telegram_bot_id": 999})
    save_settings(tmp_path, existing)
    repo = Repository(existing.database_path)
    repo.migrate()
    repo.ingest_batch([], 5)

    class Bot:
        def __init__(self, token): pass
        async def get_me(self): return SimpleNamespace(id=999, username="same")
        async def get_updates(self, **kwargs):
            pytest.fail("reconfigure must not consume pending Telegram updates")

    monkeypatch.setattr("telegram.Bot", Bot)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: "secret-token")
    answers = iter(["new destination", "", "", "dry_run"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    asyncio.run(cli.configure(tmp_path))
    assert repo.telegram_offset() == 5
    assert load_settings(tmp_path).address == "new destination"


def test_reconfigure_cannot_write_while_worker_holds_lock(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import cli
    from config import save_settings

    existing = settings(tmp_path).model_copy(update={
        "database_path": tmp_path / "private" / "assistant.db", "telegram_bot_id": 999})
    save_settings(tmp_path, existing)
    target = tmp_path / "private" / "settings.json"
    before = target.read_bytes()

    class Bot:
        def __init__(self, token): pass
        async def get_me(self): return SimpleNamespace(id=999, username="same")

    monkeypatch.setattr("telegram.Bot", Bot)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: "secret-token")
    answers = iter(["new destination", "", "", "dry_run"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    with (ProcessLock(existing.database_path.parent / "worker.lock"),
          pytest.raises(RuntimeError, match="already running")):
        asyncio.run(cli.configure(tmp_path))
    assert target.read_bytes() == before


def test_first_configuration_does_not_overwrite_configuration_created_while_binding(
        tmp_path, monkeypatch):
    from types import SimpleNamespace

    import cli
    from config import save_settings

    class Bot:
        def __init__(self, token): pass
        async def get_me(self): return SimpleNamespace(id=999, username="same")

    async def bind(*_): return 123, 1

    monkeypatch.setattr("telegram.Bot", Bot)
    monkeypatch.setattr(cli, "bind_user", bind)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: "secret-token")
    other = settings(tmp_path).model_copy(update={
        "database_path": tmp_path / "private" / "assistant.db", "telegram_bot_id": 999})
    answers = iter(["new destination", "", "", "dry_run"])

    def answer(_):
        value = next(answers)
        if value == "dry_run":
            save_settings(tmp_path, other)
        return value

    monkeypatch.setattr("builtins.input", answer)
    with pytest.raises(ValueError, match="changed during setup"):
        asyncio.run(cli.configure(tmp_path))
    assert load_settings(tmp_path).address == "private destination"


def test_reconfigure_rejects_different_bot_before_consuming_updates(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import cli
    from config import save_settings
    from storage import Repository

    existing = settings(tmp_path).model_copy(update={
        "database_path": tmp_path / "private" / "assistant.db", "telegram_bot_id": 999})
    save_settings(tmp_path, existing)
    repo = Repository(existing.database_path)
    repo.migrate()
    repo.ingest_batch([], 5)

    class Bot:
        def __init__(self, token): pass
        async def get_me(self): return SimpleNamespace(id=888, username="other")
        async def get_updates(self, **kwargs): pytest.fail("foreign bot polled")

    monkeypatch.setattr("telegram.Bot", Bot)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: "swapped-token")
    with pytest.raises(ValueError, match="bot"):
        asyncio.run(cli.configure(tmp_path))
    assert repo.telegram_offset() == 5
    assert load_settings(tmp_path).telegram_token.get_secret_value() == "secret-token"


def test_transient_poll_failure_recovers_without_losing_pending_notice(tmp_path):
    from telegram.error import NetworkError

    from domain import IncomingMessage, Intent
    from storage import Repository

    repo = Repository(tmp_path / "assistant.db")
    repo.migrate()
    repo.ingest_batch([IncomingMessage(update_id=1, user_id=123, chat_id=123, text="/lista")], 2)
    repo.apply_intent(1, Intent(action="list"), "dry_run")
    events = []

    class Recovery:
        async def recover(self): events.append("recover")

    class Checkout:
        async def run(self, order_id): pytest.fail("unexpected order")

    class IO:
        async def send_pending(self): events.append("send")
        async def poll_once(self):
            events.append("poll")
            if events.count("poll") == 1:
                raise NetworkError("offline")
            raise asyncio.CancelledError

    async def sleep(delay): events.append(("sleep", delay))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(settings(tmp_path), repo=repo, recovery=Recovery(),
                        checkout=Checkout(), transport=IO(), sleep=sleep))
    assert events == ["recover", "send", "poll", ("sleep", 1), "send", "poll"]
    assert len(repo.pending_notices()) == 1
    assert repo.telegram_offset() == 2


def test_transient_send_failure_recovers(tmp_path):
    from telegram.error import NetworkError

    from storage import Repository

    repo = Repository(tmp_path / "assistant.db")
    repo.migrate()
    events = []

    class Recovery:
        async def recover(self): pass

    class Checkout:
        async def run(self, order_id): pytest.fail("unexpected order")

    class IO:
        async def send_pending(self):
            events.append("send")
            if events.count("send") == 1:
                raise NetworkError("offline")
        async def poll_once(self): events.append("poll")

    async def sleep(delay):
        events.append(("sleep", delay))
        if delay == 0:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(settings(tmp_path), repo=repo, recovery=Recovery(),
                        checkout=Checkout(), transport=IO(), sleep=sleep))
    assert events == ["send", ("sleep", 1), "send", "poll", ("sleep", 0)]


def test_windows_acl_rejects_foreign_explicit_grant(tmp_path, monkeypatch):
    import config

    file = tmp_path / "settings.json"
    file.write_text("secret", encoding="utf-8")
    commands = []

    def invoke(args, **_):
        commands.append(args)
        if args[0] == "whoami":
            return subprocess.CompletedProcess(args, 0, '"user","S-1-5-21-123"\n', "")
        if len(commands) == 2:
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0, '{"protected":true,"owner":"S-1-5-21-123",'
                                            '"rules":[{"sid":"S-1-5-21-123","allow":true,'
                                            '"rights":2032127},{"sid":"S-1-5-21-999",'
                                            '"allow":true,"rights":2032127}]}', "")

    monkeypatch.setattr(config.subprocess, "run", invoke)
    with pytest.raises(PermissionError, match="ACL"):
        config._windows_private(file)
    assert len(commands) == 3  # Do not trust a successful mutation command without readback.


def test_windows_acl_command_failure_fails_closed(tmp_path, monkeypatch):
    import config

    def invoke(args, **_):
        if args[0] == "whoami":
            return subprocess.CompletedProcess(args, 0, '"user","S-1-5-21-123"\n', "")
        raise subprocess.CalledProcessError(1, args, output="secret: access denied")

    monkeypatch.setattr(config.subprocess, "run", invoke)
    with pytest.raises(subprocess.CalledProcessError):
        config._windows_private(tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL integration")
def test_windows_acl_removes_real_foreign_grant(tmp_path):
    from config import _READ_ACL, _windows_private

    file = tmp_path / "secret.json"
    file.write_text("dummy", encoding="utf-8")
    subprocess.run(["icacls", str(file), "/grant", "*S-1-1-0:R"],
                   capture_output=True, check=True)
    read = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _READ_ACL]
    env = {**os.environ, "SHOP_ASSISTANT_ACL_PATH": str(file)}
    import json

    before = json.loads(subprocess.run(read, env=env, capture_output=True,
                                       text=True, check=True).stdout)
    assert "S-1-1-0" in {r["sid"] for r in before["rules"]}
    _windows_private(file)
    after = json.loads(subprocess.run(read, env=env, capture_output=True,
                                      text=True, check=True).stdout)
    assert len(after["rules"]) == 1
    assert after["rules"][0]["sid"] != "S-1-1-0"


def test_rebinding_existing_owner_is_refused_before_writing(tmp_path):
    from config import save_settings

    first = settings(tmp_path).model_copy(update={"database_path": tmp_path / "private" / "db"})
    save_settings(tmp_path, first)
    with pytest.raises(ValueError, match="rebind"):
        save_settings(tmp_path, first.model_copy(update={"authorized_user_id": 456}))
    assert load_settings(tmp_path).authorized_user_id == 123


def test_old_owner_pending_order_blocks_recovery_and_checkout(tmp_path):
    from domain import IncomingMessage, Intent, IntentLine
    from storage import Repository

    repo = Repository(tmp_path / "assistant.db")
    repo.migrate()
    repo.ingest_batch([IncomingMessage(update_id=1, user_id=123, chat_id=123,
                                       text="/anadir 1 pienso")], 2)
    repo.apply_intent(1, Intent(action="add", lines=[IntentLine(description="pienso", quantity=1)]),
                      "dry_run")
    repo.ingest_batch([IncomingMessage(update_id=2, user_id=123, chat_id=123,
                                       text="/comprar")], 3)
    reply = repo.apply_intent(2, Intent(action="buy"), "dry_run")
    assert reply.order_id in repo.pending_orders()
    # A pending message and durable order from a former owner must never run under a new one.
    repo.ingest_batch([IncomingMessage(update_id=3, user_id=123, chat_id=123,
                                       text="/lista")], 4)
    events = []

    class Recovery:
        async def recover(self): events.append("recovery")

    class Checkout:
        async def run(self, order_id): events.append("checkout")

    class IO:
        async def poll_once(self): events.append("poll")
        async def send_pending(self): events.append("notice")

    class Conversation:
        async def handle(self, message, mode): events.append("dispatch")

    changed = settings(tmp_path).model_copy(update={"authorized_user_id": 456})
    with pytest.raises(PermissionError, match="owner"):
        asyncio.run(run(changed, repo=repo, recovery=Recovery(), checkout=Checkout(),
                        transport=IO(), conversation=Conversation()))
    assert events == []
    assert [m.update_id for m in repo.pending_messages()] == [3]
