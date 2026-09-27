"""Explicit private local configuration; never pass Settings to an interpreter."""

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
