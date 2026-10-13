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
    conversation_engine: Literal["legacy", "skills_agent"] = "legacy"
    guided_questions: bool = False
    agent_model: Literal["gemma4:e4b-it-q4_K_M"] = "gemma4:e4b-it-q4_K_M"
    profiles_path: Path = Path("private/profiles")
    logs_path: Path = Path("private/logs")

    @model_validator(mode="after")
    def agent_provider(self):
        if self.guided_questions and self.conversation_engine != 'skills_agent':
            raise ValueError('Guided questions require skills agent')
        if self.conversation_engine == "skills_agent" and self.model_provider != "ollama":
            raise ValueError("Skills agent requires Ollama")
        return self

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
$acl.SetOwner($sid)
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


_PRIVATE_TREE_ACL = r"""
$ErrorActionPreference = 'Stop'
$targets = [Console]::In.ReadToEnd() | ConvertFrom-Json
$setPrivate = {
""" + _SET_ACL + r"""
}
$readPrivate = {
""" + _READ_ACL + r"""
}
$count = 0
foreach ($target in $targets) {
    $item = Get-Item -LiteralPath $target.path -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or
        $item.PSIsContainer -ne $target.directory) {
        throw 'Unsafe private path'
    }
    $env:SHOP_ASSISTANT_ACL_PATH = $target.path
    $env:SHOP_ASSISTANT_ACL_DIRECTORY = if ($target.directory) { '1' } else { '0' }
    if ($env:SHOP_ASSISTANT_ACL_VERIFY_ONLY -ne '1') { & $setPrivate }
    $access = (& $readPrivate) | ConvertFrom-Json
    $rules = @($access.rules)
    $expectedInheritance = if ($target.directory) { 3 } else { 0 }
    if ($access.owner -ne $env:SHOP_ASSISTANT_ACL_SID -or $rules.Count -ne 1 -or
        $rules[0].sid -ne $env:SHOP_ASSISTANT_ACL_SID -or
        $rules[0].allow -ne $true -or $rules[0].rights -ne 2032127 -or
        ($env:SHOP_ASSISTANT_ACL_VERIFY_ONLY -ne '1' -and (
            $access.protected -ne $true -or $rules[0].inherited -ne $false -or
            $rules[0].propagation -ne 0 -or
            $rules[0].inheritance -ne $expectedInheritance))) {
        throw 'Private ACL verification failed'
    }
    $count++
}
[pscustomobject]@{ verified = $true; count = $count } | ConvertTo-Json -Compress
"""


def _windows_private_tree(paths: list[Path], *, verify_only: bool = False) -> None:
    """Verify every DACL in one process, applying it only when requested."""
    identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                              capture_output=True, text=True, check=True).stdout
    sid = next(csv.reader(identity.splitlines()))[1]
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _PRIVATE_TREE_ACL],
        env={**os.environ, "SHOP_ASSISTANT_ACL_SID": sid,
             "SHOP_ASSISTANT_ACL_VERIFY_ONLY": "1" if verify_only else "0"},
        input=json.dumps([{"path": str(path.absolute()), "directory": path.is_dir()}
                          for path in paths]),
        capture_output=True, text=True, check=True,
    )
    try:
        report = json.loads(result.stdout)
        if (not isinstance(report, dict) or report.get("verified") is not True
                or type(report.get("count")) is not int or report["count"] != len(paths)):
            raise ValueError
    except (ValueError, TypeError):
        raise PermissionError("Private ACL verification failed") from None


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
    paths = []
    pending = [directory]
    while pending:
        path = pending.pop()
        # Preflight the entire tree before any ACL mutation, without descending
        # into a link/junction. PowerShell rechecks each target before applying.
        if path.is_symlink() or (os.name == "nt" and path.is_junction()):
            raise ValueError("Private paths cannot be symlinks")
        paths.append(path)
        if path.is_dir():
            pending.extend(path.iterdir())
    if os.name == "nt":
        _windows_private_tree(paths)
    else:
        for path in paths:
            _private(path)


def _verify_private_tree(directory: Path) -> None:
    """Inspect the private tree without changing ACLs or filesystem contents."""
    paths = []
    pending = [directory]
    while pending:
        path = pending.pop()
        if path.is_symlink() or (os.name == "nt" and path.is_junction()):
            raise ValueError("Private paths cannot be symlinks")
        paths.append(path)
        if path.is_dir():
            pending.extend(path.iterdir())
    if os.name == "nt":
        try:
            _windows_private_tree(paths, verify_only=True)
        except subprocess.CalledProcessError:
            raise PermissionError("Private ACL verification failed") from None
    elif any(path.stat().st_mode & 0o077 for path in paths):
        raise PermissionError("Private permissions are too broad")


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


def load_settings(root: Path, *, read_only: bool = False) -> Settings:
    target = root / "private" / "settings.json"
    if not target.is_file() or target.is_symlink():
        raise ValueError("Missing private configuration; run python -m shop_assistant configure locally")
    if read_only:
        _verify_private_tree(root / "private")
    else:
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
