"""Report safe ACL comparison fields for a disposable CI directory."""

import csv
import json
import os
import subprocess
import tempfile
from pathlib import Path

from config import _READ_ACL, _windows_private, _windows_private_tree


def _failure_kind(error: Exception) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        stderr = error.stderr or ""
        if "CouldNotAutoloadMatchingModule" in stderr:
            return "module_autoload"
        if "Private ACL verification failed" in stderr:
            return "batch_readback_mismatch"
        if "Access is denied" in stderr or "AccessDenied" in stderr:
            return "access_denied"
        return "powershell_other"
    return type(error).__name__


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="shop-acl-ci-") as scratch:
        path = Path(scratch)
        identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                                  capture_output=True, text=True, check=True).stdout
        sid = next(csv.reader(identity.splitlines()))[1]
        try:
            _windows_private_tree([path])
            print("batch=ok")
        except Exception as error:  # noqa: BLE001 -- classify; never print path/SID
            print(f"batch={_failure_kind(error)}")

        env = {**os.environ, "SHOP_ASSISTANT_ACL_PATH": str(path)}
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _READ_ACL],
                env=env, capture_output=True, text=True, check=True,
            )
            access = json.loads(result.stdout)
            rules = access.get("rules")
            print(f"readback_json=ok protected={access.get('protected') is True} "
                  f"owner_matches={access.get('owner') == sid} "
                  f"rules_list={isinstance(rules, list)} "
                  f"rule_count={len(rules) if isinstance(rules, list) else -1}")
            if isinstance(rules, list) and len(rules) == 1:
                rule = rules[0]
                print(f"rule_sid_matches={rule.get('sid') == sid} "
                      f"allow={rule.get('allow') is True} "
                      f"rights={rule.get('rights') == 2032127} "
                      f"inherited={rule.get('inherited') is False} "
                      f"inheritance={rule.get('inheritance') == 3} "
                      f"propagation={rule.get('propagation') == 0}")
        except Exception as error:  # noqa: BLE001 -- classify; never print raw ACL
            print(f"readback={_failure_kind(error)}")

        try:
            _windows_private(path)
            print("single=ok")
        except Exception as error:  # noqa: BLE001 -- classify; never print path/SID
            print(f"single={_failure_kind(error)}")


if __name__ == "__main__":
    main()
