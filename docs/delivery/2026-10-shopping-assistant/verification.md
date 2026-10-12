# P0 verification evidence — 2026-10-12

Baseline: `b9a29049160cc53737d1cb64a8138385aa2fedd2` (checkout includes only the earlier approved documentation commit `bd1c87e`). Repair: `1c63ec11c8ada7652fe52a13daf34e75a0b7a7a5`. Author: Mushu. Independent QA pending.

## Full-suite commands and results

Use an isolated clone, the project dependency environment, UTF-8 and disposable synthetic temp paths. Before running legacy PowerShell probes, create `$env:LOCALAPPDATA/Temp/opencode` inside the synthetic environment. Set `PLAYWRIGHT_BROWSERS_PATH` to existing Chromium binaries (or install test browsers in a fresh CI runner). Do not copy private profiles or settings. The unchanged guided probe hardcodes a host temp directory; the submitted repair removes that requirement.

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
python -m pytest -q
python -m ruff check .
git diff --check
```

Initial full run exit 1: `42 failed, 1616 passed in 372.69s`.
Environment-corrected full baseline exit 1: `2 failed, 1656 passed in 444.15s`.
The two remaining failures are the v2 and v3 archive integrity tests. Their exact names appear below. No skips or deselections. Candidate focused archive/migration run: `4 passed in 6.44s`, exit 0.

## Initial failures (all retained)

```text
FAILED tests/stores/test_browser.py::test_profile_is_exclusive - playwright._...
FAILED tests/stores/test_browser.py::test_store_profiles_are_separate_and_external_navigation_blocked
FAILED tests/stores/test_browser.py::test_real_browser_redirect_chain_is_checked_each_hop
FAILED tests/stores/test_browser.py::test_launch_failure_releases_profile - p...
FAILED tests/stores/test_mercadona.py::test_existing_wrong_postcode_is_not_assumed_28023
FAILED tests/stores/test_mercadona.py::test_public_search_discovers_names_without_guessing_product_urls
FAILED tests/stores/test_nappy.py::test_promotional_quantity_requirement_is_not_silently_eligible
FAILED tests/stores/test_nappy.py::test_ambiguous_mixed_pack_rejected_from_product_fixture[Pack Dodot talla 3 con 186uds y champ\xfa infantil]
FAILED tests/stores/test_nappy.py::test_ambiguous_mixed_pack_rejected_from_product_fixture[Pa\xf1ales talla 3 con 186uds beb\xe9-seco ( 6 - 10 Kg ) Dodot con regalo sorpresa]
FAILED tests/stores/test_nappy.py::test_ambiguous_mixed_pack_rejected_from_product_fixture[Lote higiene Dodot talla 3 186uds]
FAILED tests/stores/test_nappy.py::test_ambiguous_mixed_pack_rejected_from_product_fixture[Pack Dodot 2 cajas talla 3 bebe seco con 372uds. y gel de ba\xf1o]
FAILED tests/stores/test_nappy.py::test_contradictory_or_missing_stock_evidence_is_not_available[available_for_order-0]
FAILED tests/stores/test_nappy.py::test_contradictory_or_missing_stock_evidence_is_not_available[available_for_order-None]
FAILED tests/stores/test_nappy.py::test_contradictory_or_missing_stock_evidence_is_not_available[quantity-0]
FAILED tests/stores/test_nappy.py::test_contradictory_or_missing_stock_evidence_is_not_available[quantity--1]
FAILED tests/stores/test_nappy.py::test_contradictory_or_missing_stock_evidence_is_not_available[quantity-None]
FAILED tests/stores/test_nappy.py::test_contradictory_or_missing_stock_evidence_is_not_available[quantity-True]
FAILED tests/stores/test_public_adapters.py::test_exact_product_extraction[amascotados-Amascotados-0-6399-1-12000]
FAILED tests/stores/test_public_adapters.py::test_exact_product_extraction[charro-Charro-2-2515-1-800]
FAILED tests/stores/test_public_adapters.py::test_exact_product_extraction[nappy-Nappy-1-4687-186-None]
FAILED tests/stores/test_public_adapters.py::test_exact_product_extraction[mercadona-Mercadona-1-1695-56-None]
FAILED tests/stores/test_public_adapters.py::test_out_of_stock_real_nappy_capture
FAILED tests/stores/test_public_adapters.py::test_unknown_stock_and_changed_identity_fail_closed[amascotados-Amascotados-0-6399-1-12000]
FAILED tests/stores/test_public_adapters.py::test_unknown_stock_and_changed_identity_fail_closed[charro-Charro-2-2515-1-800]
FAILED tests/stores/test_public_adapters.py::test_unknown_stock_and_changed_identity_fail_closed[nappy-Nappy-1-4687-186-None]
FAILED tests/stores/test_public_adapters.py::test_unknown_stock_and_changed_identity_fail_closed[mercadona-Mercadona-1-1695-56-None]
FAILED tests/stores/test_public_adapters.py::test_quote_refreshes_product_without_inventing_shipping
FAILED tests/test_dialogue_end_to_end.py::test_probe_exit_and_isolated_cleanup[False-0]
FAILED tests/test_dialogue_end_to_end.py::test_probe_exit_and_isolated_cleanup[True-1]
FAILED tests/test_guided_acceptance.py::test_archive_integrity_distinguishes_recorded_probe_from_current_verifier
FAILED tests/test_guided_acceptance.py::test_v3_exact_runtime_is_independently_archivable_without_hash_exemption
FAILED tests/test_natural_dialogue_probe.py::test_real_mode_does_not_substitute_interpreter
FAILED tests/test_natural_dialogue_probe.py::test_offline_exit_cleanup_and_unknown_error_metrics[flags0-0-PASS]
FAILED tests/test_natural_dialogue_probe.py::test_offline_exit_cleanup_and_unknown_error_metrics[flags1-1-FAIL]
FAILED tests/test_natural_dialogue_probe.py::test_offline_exit_cleanup_and_unknown_error_metrics[flags2-2-PENDING]
FAILED tests/test_natural_dialogue_probe.py::test_exception_orders_are_unknown
FAILED tests/test_natural_dialogue_probe.py::test_quality_cannot_pass_fallback_only
FAILED tests/test_reply_probe.py::test_probe_offline_pass_and_rejection_fallback[-Offline]
FAILED tests/test_reply_probe.py::test_probe_offline_pass_and_rejection_fallback[-OfflineReject]
FAILED tests/test_reply_probe.py::test_probe_failed_expectation_exit_one - as...
FAILED tests/test_reply_probe.py::test_probe_scenario_exception_reports_unknown_orders_and_cleans_up
FAILED tests/test_reply_probe.py::test_unavailable_service_exit_two - Asserti...
```

## Installed wheel check

Build tooling in disposable scratch: setuptools 84.0.0, wheel 0.48.0 (packaging 26.3). No project environment upgrade. Build with those tools on PYTHONPATH:

```powershell
python -m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir <wheel-output>
python -m pip install --no-index --no-deps --target <empty-installed-target> <wheel-file>
# Change cwd outside checkout; remove the source/build-tool PYTHONPATH.
$env:PYTHONPATH = '<installed-target>'
python -P <checkout>/scripts/check_installed_wheel.py --installed-root <installed-target>
```

Baseline build/install exit 0, smoke exit 1: `ModuleNotFoundError: No module named 'product_memory'` via storage -> dialogue_storage -> dialogue_controller -> dialogue_requests. CLI `--help` exits 0 despite the defect.

After adding the omitted module: build/install/smoke exit 0. Smoke output: `PASS: installed imports, skills, schema 10 and repeat migration`.

Wheel hashes are observations of these local builds, not reproducible-build guarantees:
- Baseline: `226d4d0227ac93030ad82b5866dec2dd80c42ff4bd91ecd3f8ade210c22a668d`.
- Repaired: `0c2730d491456915d673df482192cd63335552d3924281fc10b5b2bfbef1e423`.

## Probe path reproduction

Load the guided probe with `importlib`, narrow its existing literal matrix to `one-each`, set repetitions to 1, and run mode `offline` with a new scratch output. Before running, install a Python audit hook on `tempfile.mkdtemp` that rejects paths outside `Path(tempfile.gettempdir()).resolve()`; also assert all observed temporary directories are gone afterward. Baseline exit 1: `PermissionError: Probe temporary database escaped platform temp`. After using platform temp, exit 0: `PASS: synthetic probe used platform temp and cleaned up`. This measures synthetic isolation, not model quality.

## CI boundary

Workflow: `.github/workflows/offline.yml`, Windows / Python 3.12, full Git history, locked test dependencies, existing project offline suite and installed-wheel smoke. The dependency/browser setup can use network; the product tests use fixtures and no live model/Telegram/store credentials. [Initial actual run](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38262453310) was cancelled after 176 passes when concurrent staffing documentation commit `132e59c` superseded it. Run 38263025076 started for that commit; the latest candidate run remains pending. No branch protection or acceptance is implied.
