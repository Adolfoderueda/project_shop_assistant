"""Explicit private local configuration; never pass Settings to an interpreter."""

import csv
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator

from domain import Mode, Model


class Settings(Model):
    telegram_token: SecretStr = Field(repr=False)
    telegram_bot_id: int | None = None
    authorized_user_id: int
    address: str = Field(repr=False)
    postcode: str = "28023"
    mode: Mode = "dry_run"
    database_path: Path = Path("private/assistant.db")
    openai_api_key: SecretStr | None = Field(default=None, repr=False)
    openai_model: str | None = None
    model_provider: Literal["commands_only", "openai", "ollama"] = "commands_only"
    ollama_model: Literal["gemma4:e2b"] = "gemma4:e2b"
    profiles_path: Path = Path("private/profiles")
    logs_path: Path = Path("private/logs")

    @model_validator(mode="before")
    @classmethod
    def legacy_provider(cls, data):
        if isinstance(data, dict) and "model_provider" not in data:
            return {**data, "model_provider": ("openai" if data.get("openai_api_key")
                                                 and data.get("openai_model") else "commands_only")}
        return data


_SET_ACL = r"""
$ErrorActionPreference = 'Stop'
$target = $env:SHOP_ASSISTANT_ACL_PATH
$sid = New-Object System.Security.Principal.SecurityIdentifier($env:SHOP_ASSISTANT_ACL_SID)
$acl = Get-Acl -LiteralPath $target
$acl.SetAccessRuleProtection($true, $false)
foreach ($rule in @($acl.Access)) { $acl.PurgeAccessRules($rule.IdentityReference) }
$inherit = [System.Security.AccessControl.InheritanceFlags]::None
if ($env:SHOP_ASSISTANT_ACL_DIRECTORY -eq '1') {
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
               [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
}
$allow = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $sid, [System.Security.AccessControl.FileSystemRights]::FullControl, $inherit,
    [System.Security.AccessControl.PropagationFlags]::None,
    [System.Security.AccessControl.AccessControlType]::Allow)
$acl.AddAccessRule($allow)
if ($env:SHOP_ASSISTANT_ACL_DIRECTORY -eq '1') {
    [System.IO.Directory]::SetAccessControl($target, $acl)
} else {
    [System.IO.File]::SetAccessControl($target, $acl)
}
"""

_READ_ACL = r"""
$ErrorActionPreference = 'Stop'
$acl = Get-Acl -LiteralPath $env:SHOP_ASSISTANT_ACL_PATH
[pscustomobject]@{
    protected = $acl.AreAccessRulesProtected
    owner = $acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
    rules = @($acl.Access | ForEach-Object {
        [pscustomobject]@{
            sid = $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
            allow = ($_.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow)
            rights = [int]$_.FileSystemRights
            inherited = $_.IsInherited
            inheritance = [int]$_.InheritanceFlags
            propagation = [int]$_.PropagationFlags
        }
    })
} | ConvertTo-Json -Compress -Depth 4
"""


def _windows_private(path: Path) -> None:
    """Replace *all* explicit grants, then verify the effective DACL from disk."""
    identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                              capture_output=True, text=True, check=True).stdout
    sid = next(csv.reader(identity.splitlines()))[1]
    directory = path.is_dir()
    env = {**os.environ, "SHOP_ASSISTANT_ACL_PATH": str(path),
           "SHOP_ASSISTANT_ACL_SID": sid,
           "SHOP_ASSISTANT_ACL_DIRECTORY": "1" if directory else "0"}
    command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"]
    subprocess.run([*command, _SET_ACL], env=env, capture_output=True, text=True, check=True)
    result = subprocess.run([*command, _READ_ACL], env=env, capture_output=True,
                            text=True, check=True)
    try:
        access = json.loads(result.stdout)
        rules = access["rules"]
        if (access["protected"] is not True or access["owner"] != sid
                or len(rules) != 1 or rules[0] != {
                    "sid": sid, "allow": True, "rights": 2032127,
                    "inherited": False, "inheritance": 3 if directory else 0,
                    "propagation": 0,
                }):
            raise PermissionError("Private ACL verification failed")
    except (ValueError, KeyError, TypeError):
        raise PermissionError("Private ACL verification failed") from None


def _private(path: Path) -> None:
    """Restrict an existing local file or directory, failing closed on unsafe links."""
    if path.is_symlink() or (os.name == "nt" and path.is_junction()):
        raise ValueError("Private paths cannot be symlinks")
    if os.name == "nt":
        _windows_private(path)
    else:
        path.chmod(0o700 if path.is_dir() else 0o600)


def _private_tree(directory: Path) -> None:
    """Re-secure pre-existing SQLite, profiles, rotated logs and files on reconfigure."""
    _private(directory)
    for path in directory.rglob("*"):
        _private(path)


def save_settings(root: Path, settings: Settings) -> None:
    directory = root / "private"
    directory.mkdir(parents=True, exist_ok=True)
    _private_tree(directory)
    target = directory / "settings.json"
    if target.is_symlink():
        raise ValueError("Configuration cannot be a symlink")
    if target.exists():
        previous = load_settings(root)
        if previous.authorized_user_id != settings.authorized_user_id:
            raise ValueError("Cannot rebind an existing owner's data; manual review and fresh private data required")
        if (previous.telegram_bot_id is not None and previous.telegram_bot_id != settings.telegram_bot_id):
            raise ValueError("Cannot switch bot with existing offset; manual review and fresh private data required")
    fd, name = tempfile.mkstemp(prefix=".settings-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            payload = settings.model_dump(mode="json")
            payload["telegram_token"] = settings.telegram_token.get_secret_value()
            if settings.openai_api_key:
                payload["openai_api_key"] = settings.openai_api_key.get_secret_value()
            json.dump(payload, stream)
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
    _private_tree(root / "private")
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
