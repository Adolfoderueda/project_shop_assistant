"""Local console setup and diagnostics; no credentials accepted from Telegram."""

import argparse
import asyncio
import getpass
import re
import secrets
from pathlib import Path

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
    save_settings(root, Settings(telegram_token=token, authorized_user_id=user_id,
                                  address=address, postcode=postcode, mode="dry_run",
                                  database_path=Path("private/assistant.db"),
                                  openai_model=model, openai_api_key=key))
    from storage import Repository
    repo = Repository(root / "private" / "assistant.db")
    repo.migrate()
    repo.ingest_batch([], offset)
    print("Configuration stored privately. Run doctor before installing the scheduled task.")


async def doctor(root: Path) -> bool:
    try:
        settings = load_settings(root)
    except ValueError as error:
        print(str(error))
        return False
    from playwright.async_api import async_playwright
    from telegram import Bot

    from storage import Repository
    from stores.connections import registrations
    from stores.registry import StoreRegistry
    results = []
    try:
        repo = Repository(settings.database_path)
        repo.migrate()
        results.append("SQLite: OK")
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
    if not settings.openai_api_key or not settings.openai_model:
        results.append("Model: not configured; commands-only mode (not a startup blocker)")
    print("\n".join(results))
    return all("blocked" not in result for result in results[:3])


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
