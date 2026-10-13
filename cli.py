"""Local console setup and diagnostics; no credentials accepted from Telegram."""

import argparse
import asyncio
import getpass
import re
import secrets
from pathlib import Path

import httpx

from config import Settings, load_settings, save_settings


async def bind_user(bot, nonce: str) -> tuple[int, int]:
    """Discard historical updates, accept only a new direct private /start challenge."""
    old = await bot.get_updates(timeout=0, allowed_updates=["message"])
    offset = max((update.update_id for update in old), default=-1) + 1
    while True:
        updates = await bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
        for update in updates:
            offset = max(offset, update.update_id + 1)
            message = update.message
            if (message and message.text == f"/start {nonce}" and message.from_user
                    and not message.from_user.is_bot and message.chat.type == "private"
                    and message.chat.id == message.from_user.id
                    and message.forward_origin is None and message.via_bot is None
                    and message.sender_chat is None and message.sender_business_bot is None
                    and message.quote is None and not message.is_automatic_forward):
                return message.from_user.id, offset


async def configure(root: Path) -> None:
    from telegram import Bot
    token = getpass.getpass("BotFather token (hidden, local console): ").strip()
    if not token:
        raise ValueError("Token required")
    bot = Bot(token)
    info = await bot.get_me()  # No settings persisted before API verification and binding.
    target = root / "private" / "settings.json"
    previous = None
    if target.exists():
        previous = load_settings(root)
        if previous.telegram_bot_id is None:
            # Legacy settings did not retain verified bot identity. The existing
            # token is the only safe proof until this configuration is upgraded.
            if previous.telegram_token.get_secret_value() != token:
                raise ValueError("Existing bot identity unknown; token change requires manual review")
        elif previous.telegram_bot_id != info.id:
            raise ValueError("Different bot; existing Telegram offset requires manual review")
        user_id = previous.authorized_user_id
        offset = None  # Never poll/acknowledge an existing owner's offline updates.
    else:
        nonce = secrets.token_urlsafe(24)
        print(f"Open private chat with @{info.username}; send /start {nonce}. Ctrl+C to cancel.")
        user_id, offset = await bind_user(bot, nonce)
    print("Private user bound. Enter destination in this console only.")
    address = input("Full delivery address (private local file): ").strip()
    if not address:
        raise ValueError("Address required")
    postcode = input("Postcode [28023]: ").strip() or "28023"
    if postcode != "28023":
        raise ValueError("Only postcode 28023 is supported")
    model = input("Optional OpenAI model (blank = commands only): ").strip() or None
    key = (getpass.getpass("Optional OpenAI API key (hidden): ").strip() or None) if model else None
    if bool(model) != bool(key):
        raise ValueError("Model and key must be provided together")
    # Live capability is blocked at checkout until independently verified by every store.
    print("Default dry_run: no actual purchases. Live mode requires separate capability verification.")
    choice = input("Type dry_run to confirm local configuration: ").strip()
    if choice != "dry_run":
        raise ValueError("Configuration cancelled; no schedule or live mode enabled")
    from runtime import ProcessLock

    lock_path = (previous.database_path.parent if previous is not None
                 else root / "private") / "worker.lock"
    with ProcessLock(lock_path):
        if target.exists():
            if previous is None:
                raise ValueError("Configuration changed during setup; retry")
            current = load_settings(root)
            if (current.database_path != previous.database_path
                    or current.authorized_user_id != user_id
                    or current.telegram_bot_id not in (None, info.id)):
                raise ValueError("Configuration changed during setup; retry")
        save_settings(root, Settings(telegram_token=token, telegram_bot_id=info.id,
                                      authorized_user_id=user_id,
                                      address=address, postcode=postcode, mode="dry_run",
                                      database_path=Path("private/assistant.db"),
                                      openai_model=model, openai_api_key=key))
    from storage import Repository
    repo = Repository(root / "private" / "assistant.db")
    repo.migrate()
    if offset is not None:
        repo.ingest_batch([], offset)
    print("Configuration stored privately. Run doctor before installing the scheduled task.")


async def doctor(root: Path) -> bool:
    try:
        settings = load_settings(root, read_only=True)
    except (ValueError, PermissionError) as error:
        print(str(error))
        return False
    from playwright.async_api import async_playwright
    from telegram import Bot

    from storage import SCHEMA_VERSION, Repository
    from stores.connections import registrations
    from stores.registry import StoreRegistry
    results = []
    try:
        repo = Repository(settings.database_path)
        if repo.schema_version() == SCHEMA_VERSION:
            results.append("SQLite: OK")
        else:
            results.append("SQLite: blocked (schema update required)")
    except Exception:  # noqa: BLE001 -- no raw SQLite details, paths may be private
        results.append("SQLite: blocked (check private directory permissions and migration)")
    try:
        await Bot(settings.telegram_token.get_secret_value()).get_me()
        results.append("Telegram API: OK")
    except Exception:  # noqa: BLE001 -- HTTP errors can contain token
        results.append("Telegram API: blocked (check token and network locally)")
    try:
        async with async_playwright() as playwright:
            if not Path(playwright.chromium.executable_path).is_file():
                raise FileNotFoundError
        results.append("Chromium: installed (visible login requires desktop session)")
    except Exception:  # noqa: BLE001 -- no raw browser paths in diagnostics
        results.append("Chromium: blocked (run python -m playwright install chromium)")
    registry = StoreRegistry(registrations())
    for store_id, adapter in registry.adapters.items():
        caps = adapter.capabilities()
        results.append(f"{store_id}: search={caps.search}, quote={caps.quote}, "
                       f"prepare={caps.prepare}, submit={caps.submit}, "
                       f"reconcile={caps.reconcile}, live_verified={caps.live_verified}; "
                       "shipping/total/destination not verified")
    results.append(f"Engine: {settings.conversation_engine}; model: "
                   f"{settings.agent_model if settings.conversation_engine == 'skills_agent' else settings.ollama_model}")
    if settings.model_provider == "ollama":
        model = settings.agent_model if settings.conversation_engine == 'skills_agent' else settings.ollama_model
        results.append("Model: Ollama local available" if await ollama_available(model)
                       else "Model: Ollama local blocked; commands remain available")
    elif settings.model_provider == "commands_only":
        results.append("Model: not configured; commands-only mode (not a startup blocker)")
    print("\n".join(results))
    return all("blocked" not in result for result in results[:3])


async def ollama_available(model: str, *, transport=None) -> bool:
    """Check a fixed loopback endpoint only; never trust proxy settings or redirects."""
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11434", trust_env=False,
                                     follow_redirects=False, timeout=httpx.Timeout(5.0, connect=2.0),
                                     transport=transport) as client:
            response = await client.get("/api/tags", follow_redirects=False)
            if response.status_code != 200:
                return False
            data = response.json()
            models = data["models"]
            return isinstance(models, list) and any(
                isinstance(item, dict) and item.get("name") == model for item in models)
    except Exception:  # noqa: BLE001 -- HTTP errors may include private details
        return False


async def model_local(root: Path, action: str) -> bool:
    return await _local_engine(root, action, agent=False)


async def agent_local(root: Path, action: str) -> bool:
    return await _local_engine(root, action, agent=True)


async def guided_local(root: Path, action: str) -> bool:
    """Change guided permission with the worker stopped; status performs no writes."""
    from runtime import ProcessLock

    if action not in {'status', 'enable', 'disable'}:
        raise ValueError('Invalid local action')
    initial = load_settings(root)
    if action == 'status':
        print(f'Guided questions: {"enabled" if initial.guided_questions else "disabled"}; '
              f'engine: {initial.conversation_engine}; provider: {initial.model_provider}')
        return True
    try:
        lock = ProcessLock(initial.database_path.parent / 'worker.lock')
        lock.__enter__()
    except RuntimeError:
        print('Worker is running; stop the worker before changing guided questions, then retry.')
        return False
    try:
        settings = load_settings(root)
        if settings.database_path != initial.database_path:
            raise ValueError('Database lock target changed; configuration unchanged')
        if action == 'enable' and (
                settings.conversation_engine != 'skills_agent' or settings.model_provider != 'ollama'
                or not await ollama_available(settings.agent_model)):
            print('Guided questions require skills_agent, Ollama and the available E4B model; configuration unchanged.')
            return False
        updated = Settings.model_validate(settings.model_copy(update={
            'guided_questions': action == 'enable'}).model_dump())
        from storage import Repository
        repo = Repository(settings.database_path)
        repo.migrate()
        repo.assert_authorized_owner(settings.authorized_user_id)
        repo.revoke_agent_proposals()
        save_settings(root, updated)
        print(f'Guided questions: {"enabled" if updated.guided_questions else "disabled"}. '
              'Pending permissions revoked; saved lines unchanged. Restart the worker to apply. '
              'Rollback uses this code with questions disabled, never a schema downgrade.')
        return True
    finally:
        lock.__exit__(None, None, None)


async def _local_engine(root: Path, action: str, *, agent: bool) -> bool:
    from runtime import ProcessLock

    if action not in {'status', 'enable', 'disable'}:
        raise ValueError('Invalid local action')
    initial = load_settings(root)
    if action == 'status':
        print(f"Engine: {initial.conversation_engine}; provider: {initial.model_provider}")
        model = initial.agent_model if agent else initial.ollama_model
        print(f"Model: {model}")
        if initial.model_provider == 'ollama':
            print('Ollama local: available' if await ollama_available(model)
                  else 'Ollama local: unavailable; commands still work')
        return True
    try:
        lock = ProcessLock(initial.database_path.parent / "worker.lock")
        lock.__enter__()
    except RuntimeError:
        print("Worker is running; stop the worker before changing the local model, then retry.")
        return False
    try:
        settings = load_settings(root)
        if settings.database_path != initial.database_path:
            raise ValueError("Database lock target changed; configuration unchanged")
        if action == "enable":
            if not await ollama_available(settings.agent_model if agent else settings.ollama_model):
                print("Ollama local unavailable or model missing; configuration unchanged.")
                return False
            provider = "ollama"
        else:
            provider = "commands_only"
        updates = {'model_provider': provider}
        if agent:
            updates = {'conversation_engine': 'skills_agent' if action == 'enable' else 'legacy'}
            if action == 'enable':
                updates['model_provider'] = 'ollama'
        elif action == 'disable':
            updates['conversation_engine'] = 'legacy'
        if action == 'disable':
            updates['guided_questions'] = False
        updated = Settings.model_validate(settings.model_copy(update=updates).model_dump())
        if agent or action == 'disable':
            from storage import Repository
            repo = Repository(settings.database_path)
            repo.migrate()
            repo.assert_authorized_owner(settings.authorized_user_id)
            repo.revoke_agent_proposals()
        save_settings(root, updated)
        print(f"Engine: {updated.conversation_engine}; provider: {updated.model_provider}. "
              "Restart the worker to apply; Telegram binding unchanged. Agent permission revoked "
              "when switching engines; review a new proposal before confirming.")
        return True
    finally:
        lock.__exit__(None, None, None)


async def login(root: Path, store_id: str) -> None:
    settings = load_settings(root)
    from stores.browser import BrowserManager
    from stores.connections import registrations
    from stores.registry import StoreRegistry
    registry = StoreRegistry(registrations())
    registration = registry.get(store_id)
    manager = BrowserManager(settings.profiles_path, registry)
    try:
        context = await manager.open(store_id)
        print("Dedicated visible profile opened. Authenticate manually in browser only; no passwords here.")
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://" + min(registration.navigation_hosts))
        await asyncio.to_thread(input, "Press Enter after closing login interaction: ")
    finally:
        await manager.close()


def verify_product(root: Path, product_id: str) -> None:
    if product_id != "formula":
        raise ValueError("Only formula can be manually verified with this command")
    settings = load_settings(root)
    from storage import Repository
    repo = Repository(settings.database_path)
    repo.migrate()
    print("Check physical label AND independent manufacturer's reference; Optimum is not assumed Evolution.")
    name = input("Exact product name on label: ").strip()
    if name.casefold() != "blemil evolution 1":
        raise ValueError("Reference mismatch: expected Blemil Evolution 1; not marked verified")
    gtin = input("GTIN read from product label (digits): ").strip()
    if not re.fullmatch(r"\d{8}|\d{12,14}", gtin):
        raise ValueError("Valid physical label GTIN required")
    source = input("Independent manufacturer reference checked (describe locally): ").strip()
    if not source:
        raise ValueError("Independent check required")
    confirm = input("Type VERIFY to attest label and independent reference agree: ").strip()
    if confirm != "VERIFY":
        raise ValueError("Verification cancelled")
    repo.verify_formula(gtin)
    print("Local formula rule verified; store offer identity and checkout remain independently blocked.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m shop_assistant")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("configure", "doctor", "run"):
        sub.add_parser(command)
    login_parser = sub.add_parser("login")
    login_parser.add_argument("--store", required=True)
    verify_parser = sub.add_parser("verify-product")
    verify_parser.add_argument("--id", required=True)
    local_parser = sub.add_parser("model-local")
    local_parser.add_argument("action", choices=("enable", "disable", "status"))
    agent_parser = sub.add_parser('agent-local')
    agent_parser.add_argument('action', choices=('enable', 'disable', 'status'))
    questions_parser = sub.add_parser('questions-local')
    questions_parser.add_argument('action', choices=('enable', 'disable', 'status'))
    args = parser.parse_args(argv)
    root = Path.cwd().resolve()
    try:
        if args.command == "configure":
            asyncio.run(configure(root))
        elif args.command == "doctor":
            return 0 if asyncio.run(doctor(root)) else 1
        elif args.command == "run":
            from runtime import configure_logging, run
            settings = load_settings(root)
            configure_logging(settings)
            asyncio.run(run(settings))
        elif args.command == "login":
            asyncio.run(login(root, args.store))
        elif args.command == "model-local":
            return 0 if asyncio.run(model_local(root, args.action)) else 1
        elif args.command == 'agent-local':
            return 0 if asyncio.run(agent_local(root, args.action)) else 1
        elif args.command == 'questions-local':
            return 0 if asyncio.run(guided_local(root, args.action)) else 1
        else:
            verify_product(root, args.id)
    except KeyboardInterrupt:
        print("Stopped; pending work remains durable.")
        return 0
    except Exception:  # noqa: BLE001 -- never print third-party error bodies/secrets
        # Never print exception details from HTTP/browser/configuration (may contain secrets).
        print("Operation blocked; inspect local configuration, browser and connectivity with doctor.")
        return 1
    return 0
