# FACO Parallel Shard Validation — 2026-11-20

## Result

**74 passed, 0 failed** across three concurrently launched test shards in the existing Vercel staging Sandbox.

| Shard | Test files | Result |
|---|---|---:|
| bridge | test_capability_mesh.py, test_mcp_server.py | 35 passed |
| governance | test_service_emulation_governance.py, test_service_emulation_planner.py | 22 passed |
| adapters | test_koofr_webdav_adapter.py | 17 passed |
| **Total** | **5 test files** | **74 passed, 0 failed** |

## Environment

- Provider: Vercel Sandbox (existing staging sandbox)
- Runtime: Python 3.14.4
- Resources: 1 vCPU, 2 GiB memory
- Source branch: `flybrain-browser-worker-staging`
- Source commit: `5855eca63343b46612d811494ee1ac2da1bc726f`
- Release ZIP extraction: passed
- Bridge overlay application: passed
- `compileall`: passed
- Test shards: launched concurrently as three background pytest processes
- Sandbox was stopped after validation to release compute.

## GitHub Actions matrix result

The staging workflow was changed to a three-shard matrix with max-parallel=3. GitHub expanded all three jobs, confirming the matrix configuration was parsed. The run failed before the first step in every job:

- runner_id: 0
- runner_name: empty
- steps: empty

Therefore, GitHub-hosted runner provisioning failed before checkout/setup/test. This is not a code-level test failure, and no Python 3.12 test result is claimed.

## Limitations

- These results qualify the test suite on Python 3.14.4 only.
- Python 3.12 compatibility remains open.
- The Vercel fallback used one 1-vCPU sandbox; concurrent test processes do not imply three independent cloud machines.
- The separate scheduled end-to-end continuity qualification remains in progress.
