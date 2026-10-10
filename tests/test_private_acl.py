"""Private-tree protection must stay strict without per-file process startup."""

import json
import os
import subprocess

import pytest

import config


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL integration")
def test_private_tree_secures_every_path_with_one_powershell_process(tmp_path, monkeypatch):
    root = tmp_path / "private"
    nested = root / "profiles" / "cache"
    nested.mkdir(parents=True)
    (root / "settings.json").write_text("dummy", encoding="utf-8")
    (nested / "first.bin").write_bytes(b"dummy")
    (nested / "second ' [ñ].bin").write_bytes(b"dummy")
    subprocess.run(["icacls", str(root), "/grant", "*S-1-1-0:R", "/T"],
                   capture_output=True, check=True)
    original_run = subprocess.run
    commands = []

    def counted_run(args, **kwargs):
        commands.append(args)
        return original_run(args, **kwargs)

    monkeypatch.setattr(config.subprocess, "run", counted_run)
    config._private_tree(root)
    assert sum(command[0] == "powershell.exe" for command in commands) == 1
    assert sum(command[0] == "whoami" for command in commands) <= 1

    # Independent readback from Windows, not the batch's own success report.
    script = r"""
    $ErrorActionPreference = 'Stop'
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $targets = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $results = @(foreach ($target in $targets) {
        $acl = Get-Acl -LiteralPath $target
        [pscustomobject]@{
            path = $target
            protected = $acl.AreAccessRulesProtected
            owner = $acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
            rules = @($acl.Access | ForEach-Object {
                [pscustomobject]@{
                    sid = $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
                    allow = ($_.AccessControlType -eq 'Allow')
                    rights = [int]$_.FileSystemRights
                    inherited = $_.IsInherited
                    inheritance = [int]$_.InheritanceFlags
                    propagation = [int]$_.PropagationFlags
                }
            })
        }
    })
    ConvertTo-Json -InputObject $results -Depth 5 -Compress
    """
    paths = [root, *root.rglob("*")]
    result = original_run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        input=json.dumps([str(path) for path in paths]),
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    access = json.loads(result.stdout)
    assert len(access) == len(paths)
    for item in access:
        path = next(path for path in paths if str(path) == item["path"])
        assert item["protected"] is True
        assert item["rules"] == [{
            "sid": item["owner"], "allow": True, "rights": 2032127,
            "inherited": False, "inheritance": 3 if path.is_dir() else 0,
            "propagation": 0,
        }]
        assert item["owner"] != "S-1-1-0"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction integration")
def test_private_tree_rejects_junction_before_changing_any_permissions(tmp_path, monkeypatch):
    root = tmp_path / "private"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "untouched.txt").write_text("dummy", encoding="utf-8")
    junction = root / "linked"
    subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(junction), str(outside)],
                   capture_output=True, check=True)

    def forbidden_run(*args, **kwargs):
        pytest.fail("Unsafe tree must be rejected before permission changes")

    monkeypatch.setattr(config.subprocess, "run", forbidden_run)
    try:
        with pytest.raises(ValueError, match="symlinks"):
            config._private_tree(root)
    finally:
        junction.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="Windows batch boundary")
@pytest.mark.parametrize("report", ["", '{"verified":false,"count":1}',
                                    '{"verified":true,"count":0}'])
def test_private_tree_rejects_missing_or_partial_readback(tmp_path, monkeypatch, report):
    root = tmp_path / "private"
    root.mkdir()

    def invoke(args, **kwargs):
        output = '"user","S-1-5-21-123"\n' if args[0] == "whoami" else report
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(config.subprocess, "run", invoke)
    with pytest.raises(PermissionError, match="ACL"):
        config._private_tree(root)


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL integration")
def test_private_tree_readback_detects_foreign_grant_when_mutation_does_not_apply(
    tmp_path, monkeypatch,
):
    root = tmp_path / "private"
    root.mkdir()
    subprocess.run(["icacls", str(root), "/grant", "*S-1-1-0:R"],
                   capture_output=True, check=True)
    # Fault injection: a successful setter that did not actually secure the DACL.
    monkeypatch.setattr(config, "_PRIVATE_TREE_ACL",
                        config._PRIVATE_TREE_ACL.replace(config._SET_ACL, ""))
    with pytest.raises(subprocess.CalledProcessError) as error:
        config._private_tree(root)
    assert "Private ACL verification failed" in error.value.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows batch boundary")
def test_private_tree_command_failure_fails_closed(tmp_path, monkeypatch):
    root = tmp_path / "private"
    root.mkdir()

    def invoke(args, **kwargs):
        if args[0] == "whoami":
            return subprocess.CompletedProcess(args, 0, '"user","S-1-5-21-123"\n', "")
        raise subprocess.CalledProcessError(1, args, output="dummy access denied")

    monkeypatch.setattr(config.subprocess, "run", invoke)
    with pytest.raises(subprocess.CalledProcessError):
        config._private_tree(root)


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL readback")
def test_private_tree_rejects_wrong_propagation_flags(tmp_path, monkeypatch):
    root = tmp_path / "private"
    root.mkdir()
    # Inject a readback with an InheritOnly ACE instead of the exact required DACL.
    monkeypatch.setattr(config, "_PRIVATE_TREE_ACL", config._PRIVATE_TREE_ACL.replace(
        "propagation = [int]$_.PropagationFlags", "propagation = 2",
    ))
    with pytest.raises(subprocess.CalledProcessError) as error:
        config._private_tree(root)
    assert "Private ACL verification failed" in error.value.stderr
