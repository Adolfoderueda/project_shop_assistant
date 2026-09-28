"""Explicit private local configuration; never pass Settings to an interpreter."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from pydantic import Field, SecretStr

from domain import Mode, Model


class Settings(Model):
    telegram_token: SecretStr = Field(repr=False)
    authorized_user_id: int
    address: str = Field(repr=False)
    postcode: str = "28023"
    mode: Mode = "dry_run"
    database_path: Path = Path("private/assistant.db")
    openai_api_key: SecretStr | None = Field(default=None, repr=False)
    openai_model: str | None = None
    profiles_path: Path = Path("private/profiles")
    logs_path: Path = Path("private/logs")


def _private(path: Path) -> None:
    """Restrict local files to the logged-on user; fail closed if ACL setup fails."""
    if os.name == "nt":
        identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                                  capture_output=True, text=True, check=True).stdout
        import csv
        sid = next(csv.reader(identity.splitlines()))[1]
        grant = f"*{sid}:(OI)(CI)F" if path.is_dir() else f"*{sid}:F"
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", grant],
                       capture_output=True, check=True)
    else:
        path.chmod(0o700 if path.is_dir() else 0o600)


def save_settings(root: Path, settings: Settings) -> None:
    directory = root / "private"
    directory.mkdir(parents=True, exist_ok=True)
    _private(directory)
    target = directory / "settings.json"
    if target.is_symlink():
        raise ValueError("Configuration cannot be a symlink")
    fd, name = tempfile.mkstemp(prefix=".settings-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(settings.model_dump(mode="json"), stream)
            stream.flush()
            os.fsync(stream.fileno())
        _private(Path(name))
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load_settings(root: Path) -> Settings:
    target = root / "private" / "settings.json"
    if not target.is_file() or target.is_symlink():
        raise ValueError("Missing private configuration; run python -m shop_assistant configure locally")
    try:
        settings = Settings.model_validate_json(target.read_text(encoding="utf-8"))
        if (settings.authorized_user_id <= 0 or not settings.telegram_token.get_secret_value()
                or not settings.address.strip() or settings.postcode != "28023"):
            raise ValueError("Incomplete configuration")
        return settings.model_copy(update={
            "database_path": _local_path(root, settings.database_path),
            "profiles_path": _local_path(root, settings.profiles_path),
            "logs_path": _local_path(root, settings.logs_path),
        })
    except (ValueError, OSError):
        raise ValueError("Invalid private configuration; run python -m shop_assistant configure locally") from None


def _local_path(root: Path, path: Path) -> Path:
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve() / "private"):
        raise ValueError("Data paths must stay under private/")
    return resolved
