# FlyBrain External Sandbox Test Report

- Date: 2026-11-20
- Repository: `ramysaid721-sudo/FlyBrain-Research-Platform`
- Branch: `flybrain-browser-worker-staging`
- Tested source head: `2f8025ecb5655d050da7a723cee6a16b32598e4f`
- Runtime: Vercel Sandbox Hobby, 1 vCPU, 2 GiB RAM, Python 3.14.4
- Scope: staging only; no production deployment or external paid service use

## Result

**74 passed, 0 failed.**

The run also completed:

```bash
python -m compileall -q bridge scripts
```

The test suite was run against the release ZIP after applying the repository bridge overlay:

```bash
python -m zipfile -e FlyBrain_Research_Platform_Fresh_Install_v0.14.0.zip .release
python scripts/apply_chat_bridge.py --source .release/FlyBrain_Research_Platform_v0.14.0
python -m pytest -q \
  components/FlyBrain-NOS/tests/test_capability_mesh.py \
  components/FlyBrain-NOS/tests/test_mcp_server.py \
  components/FlyBrain-NOS/tests/test_service_emulation_governance.py \
  components/FlyBrain-NOS/tests/test_service_emulation_planner.py \
  components/FlyBrain-NOS/tests/test_koofr_webdav_adapter.py
```

## Defects found and corrected

1. `bridge/mcp_server.py`: a JSON-style lowercase `false` was used as a Python value in a tool input schema. This raised `NameError` while handling `tools/list`. Replaced it with Python's `False`.
2. `bridge/browser_use_adapter.py`: Browserless URL/DNS validation ran before checking whether credentials and explicit usage opt-in were configured. Reordered the checks so the adapter fails closed before network-dependent validation.

## Verification boundary

- The source was fetched from the updated staging branch after both fixes were committed, then the release overlay was rebuilt and the 74-test suite passed again.
- This sandbox used Python 3.14.4. The GitHub Actions workflow specifies Python 3.12, so a Python 3.12 run remains a separate compatibility check.
- This test run does not prove GitHub Actions runner provisioning is repaired; the earlier GitHub Actions jobs failed before their first step.
- No secrets or credentials are included in this report.
