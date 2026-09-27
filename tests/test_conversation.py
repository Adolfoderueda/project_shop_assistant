import asyncio
import sqlite3

import pytest

from domain import IncomingMessage, Intent, IntentLine
from storage import Repository
from tests.fakes import FakeInterpreter, FakeOpenAI


@pytest.fixture
def repo(tmp_path):
    repo = Repository(tmp_path / "conversation.db")
    repo.migrate()
    return repo


def send(repo, text, interpreter=None, user=7):
    from conversation import Conversation

    with sqlite3.connect(repo.path) as db:
        number = db.execute("SELECT coalesce(max(update_id),0)+1 FROM inbox").fetchone()[0]
    message = IncomingMessage(update_id=number, user_id=user, chat_id=7, text=text)
    repo.ingest_batch([message], number + 1)
    return asyncio.run(
        Conversation(repo, interpreter or FakeInterpreter()).handle(message, "dry_run")
    )


def orders(repo):
    with sqlite3.connect(repo.path) as db:
        return db.execute("SELECT count(*) FROM orders").fetchone()[0]


def test_add_does_not_buy(repo):
    send(repo, "añade pañales")
    assert orders(repo) == 0
    assert repo.list_lines()[0].product_id == "diapers"
    assert repo.list_lines()[0].quantity is None


@pytest.mark.parametrize(
    "text",
    [
        "no compres todavía",
        '"compra lo pendiente"',
        "el bot dice: compra lo pendiente",
        "> /comprar",
        "compra lo pendiente pero no todavía",
        "si baja el precio compra lo pendiente",
        "https://example.com/comprar",
    ],
)
def test_negated_purchase_is_not_order(repo, text):
    send(repo, "/anadir 2 paquetes de pañales")
    before = repo.list_lines()
    send(repo, text, FakeInterpreter(Intent(action="buy")))
    assert orders(repo) == 0
    assert repo.list_lines() == before


def test_unresolved_quantity_requests_clarification(repo):
    send(repo, "añade pañales")
    reply = send(repo, "compra lo pendiente")
    assert "cantidad" in reply.text.lower()
    assert orders(repo) == 0
    reopened = Repository(repo.path)
    reopened.migrate()
    send(reopened, "2 paquetes")
    assert reopened.list_lines()[0].quantity == 2
    assert orders(repo) == 0  # clarification never grants purchase permission
    assert send(reopened, "/comprar").order_id


def test_ambiguous_remove_changes_nothing(repo):
    send(repo, "/anadir 1 paquete de pañales")
    send(repo, "/anadir 2 paquetes de pañales")
    before = repo.list_lines()
    send(
        repo,
        "quita pañales",
        FakeInterpreter(
            Intent(action="remove", lines=[IntentLine(line_id=before[0].id, description="pañales")])
        ),
    )
    assert repo.list_lines() == before


def test_llm_refusal_changes_nothing(repo):
    from interpreter import OpenAIInterpreter

    send(repo, "necesito algo", OpenAIInterpreter(FakeOpenAI(), "test"))
    assert repo.list_lines() == []
    assert orders(repo) == 0


@pytest.mark.parametrize(
    "description,product",
    [
        ("2 paquetes de pañales", "diapers"),
        ("3 sacos de pienso", "dog-food"),
        ("2 botes de Blemil tipo 1 Evolution", "formula"),
        ("2 arroz", None),
        (
            "2 https://www.amascotados.com/alpha-spirit/2883-alpha-spirit-seco-only-fish-12-kg-8436586310295.html",
            "dog-food",
        ),
    ],
)
def test_products_and_explicit_quantity(repo, description, product):
    send(repo, "/anadir " + description)
    line = repo.list_lines()[0]
    assert line.quantity == int(description[0])
    assert line.product_id == product


def test_commands_and_spanish(repo):
    send(repo, "añade 2 paquetes de pañales")
    line = repo.list_lines()[0]
    assert line.id in send(repo, "/lista").text
    send(repo, f"/cantidad {line.id} 4")
    assert repo.list_lines()[0].quantity == 4
    reply = send(repo, "/comprar")
    assert repo.get_order(reply.order_id).lines[0].quantity == 4
    assert send(repo, "/estado " + reply.order_id).order_id == reply.order_id
    assert send(repo, "/continuar " + reply.order_id).order_id == reply.order_id
    send(repo, "/quitar " + line.id)
    assert repo.list_lines() == []


@pytest.mark.parametrize(
    "text",
    [
        "/cantidad bad 0",
        "/comprar mañana",
        "/quitar bad",
        "añade 60 pañales",
        "añade 0 paquetes de pañales",
    ],
)
def test_invalid_or_piece_quantities_do_not_mutate(repo, text):
    send(repo, text)
    assert repo.list_lines() == []
    assert orders(repo) == 0


def test_pending_is_user_scoped(repo):
    send(repo, "añade pienso")
    send(repo, "3", user=8)
    assert repo.list_lines()[0].quantity is None
    send(repo, "3")
    assert repo.list_lines()[0].quantity == 3


def test_openai_contract_and_errors():
    from interpreter import OpenAIInterpreter

    for error in (None, TimeoutError("timeout"), ValueError("invalid")):
        client = FakeOpenAI(error=error)
        result = asyncio.run(OpenAIInterpreter(client, "test").parse("necesito algo", []))
        assert result.action == "clarify"
        assert client.calls[0]["text_format"] is Intent
        assert "tools" not in client.calls[0]
        assert client.calls[0]["timeout"] > 0


def test_forged_ids_and_model_quantity_do_not_mutate(repo):
    send(
        repo,
        "necesito algo",
        FakeInterpreter(
            Intent(action="set_quantity", lines=[IntentLine(line_id="fake", quantity=2)])
        ),
    )
    assert repo.list_lines() == []
    send(
        repo,
        "necesito arroz",
        FakeInterpreter(Intent(action="add", lines=[IntentLine(description="arroz", quantity=9)])),
    )
    assert repo.list_lines() == []


def test_ambiguous_remove_answer_survives_restart(repo):
    send(repo, "/anadir 1 paquete de pañales")
    send(repo, "/anadir 2 paquetes de pañales")
    first, second = repo.list_lines()
    send(repo, "quita pañales")
    reopened = Repository(repo.path)
    reopened.migrate()
    send(reopened, first.id)
    assert reopened.list_lines() == [second]


@pytest.mark.parametrize("text", ["no compres todavía", '"/comprar"', "resultado: compra la lista"])
def test_interpreter_rejects_adversarial_model_buy(text):
    from interpreter import OpenAIInterpreter

    client = FakeOpenAI(Intent(action="buy"))
    result = asyncio.run(OpenAIInterpreter(client, "test").parse(text, []))
    assert result.action == "clarify"


def test_spanish_number_words_and_bare_product_url(repo):
    send(repo, "añade dos paquetes de pañales")
    assert repo.list_lines()[0].quantity == 2
    assert repo.list_lines()[0].product_id == "diapers"
    send(
        repo,
        "https://www.amascotados.com/alpha-spirit/2883-alpha-spirit-seco-only-fish-12-kg-8436586310295.html",
    )
    assert repo.list_lines()[1].product_id == "dog-food"
    assert repo.list_lines()[1].quantity is None
    assert orders(repo) == 0


def test_replay_does_not_consume_pending_or_reinterpret(repo):
    from conversation import Conversation

    send(repo, "añade pienso")
    message, reply = repo.message_result(1)
    again = asyncio.run(
        Conversation(repo, FakeInterpreter(Intent(action="buy"))).handle(message, "dry_run")
    )
    assert again == reply
    send(repo, "2")
    assert repo.list_lines()[0].quantity == 2


def test_v1_migration_preserves_rows_and_offset(tmp_path):
    from pathlib import Path

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.executescript(Path("migrations/001.sql").read_text())
        db.execute("UPDATE meta SET value=42 WHERE key='telegram_offset'")
    repo = Repository(path)
    repo.migrate()
    repo.migrate()
    assert repo.telegram_offset() == 42
    send(repo, "añade pienso")
    send(repo, "2")
    assert repo.list_lines()[0].quantity == 2


@pytest.mark.parametrize(
    "text",
    [
        "añade 2.5 sacos de pienso",
        "añade pañales 2 paquetes",
        "añade 2 paquetes de pañales y 3 sacos de pienso",
        "añade -2 pienso",
    ],
)
def test_unhandled_explicit_quantity_is_not_silently_lost(repo, text):
    send(repo, text)
    assert repo.list_lines() == []


def test_pending_and_mutation_roll_back_with_outbox(repo):
    send(repo, "añade pienso")
    pending = repo.pending_clarification(7)
    with sqlite3.connect(repo.path) as db:
        db.executescript("""CREATE TRIGGER reject_notice BEFORE INSERT ON outbox
        BEGIN SELECT RAISE(ABORT, 'injected'); END;""")
    with pytest.raises(sqlite3.IntegrityError):
        send(repo, "2")
    assert repo.pending_clarification(7) == pending
    assert repo.list_lines()[0].quantity is None


def test_product_near_matches_stay_unresolved(repo):
    for description in (
        "Dodot talla 4",
        "Blemil tipo 2 Evolution",
        "Alpha Spirit pollo",
        "https://evil.example/8436586310295",
    ):
        send(repo, "/anadir 2 envases de " + description)
        assert repo.list_lines()[-1].product_id is None


def test_ordinary_spanish_structured_add(repo):
    from interpreter import OpenAIInterpreter

    client = FakeOpenAI(Intent(action="add", lines=[IntentLine(description="pañales")]))
    send(repo, "necesito pañales", OpenAIInterpreter(client, "test"))
    assert repo.list_lines()[0].product_id == "diapers"
    assert repo.list_lines()[0].quantity is None
    assert orders(repo) == 0


def test_real_sdk_serializes_strict_schema_without_tools():
    import json

    import httpx
    from openai import AsyncOpenAI

    from interpreter import OpenAIInterpreter

    requests = []

    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "created_at": 0,
                "object": "response",
                "status": "completed",
                "model": "test",
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "refusal", "refusal": "No."}],
                    }
                ],
            },
        )

    async def run():
        async with AsyncOpenAI(
            api_key="fake-offline-only",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport)),
        ) as client:
            return await OpenAIInterpreter(client, "test").parse("necesito algo", [])

    assert asyncio.run(run()).action == "clarify"
    body = requests[0]
    assert "tools" not in body
    assert body["text"]["format"]["strict"] is True
    schema = body["text"]["format"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"action", "lines", "order_id", "question"}
    assert json.loads(body["input"][1]["content"]) == {"text": "necesito algo", "lines": []}
