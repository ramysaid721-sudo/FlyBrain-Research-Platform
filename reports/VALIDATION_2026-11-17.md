# FlyBrain Research Platform — Fresh Source Validation

**Date:** 2026-11-17  
**Release archive:** `FlyBrain_Research_Platform_Fresh_Install_v0.14.0.zip`  
**Runtime:** Python 3.13.5

## Source integrity
- Retrieved the exact release archive from the repository's corresponding Library copy.
- ZIP integrity check: PASS (`ZipFile.testzip()` returned no corrupt member).
- Archive entries: 129.
- Extracted into an isolated audit directory; the archive itself was not modified.

## Fresh test execution
The execution environment had no outbound package-index connectivity. Editable installation therefore could not download the isolated PEP 517 build requirement `setuptools>=68`. To avoid substituting or modifying package code, tests were executed directly against the extracted source using explicit `PYTHONPATH` entries for URCAL, FlyBrain-NOS, and the adapter.

| Check | Result |
|---|---:|
| URCAL test suite | 68 passed, 0 failed |
| FlyBrain-NOS + URCAL integration-enabled suite | 76 passed, 0 failed |
| Python compileall for URCAL, FlyBrain-NOS, adapter | Passed |
| Import smoke test (`urcal`, `flybrain_os`, `flybrain_urcal_adapter`) | `ALL IMPORTS PASSED` |

These are fresh source-level checks in Python 3.13.5. They do not constitute a successful wheel build, clean target installation, or multi-version CI run.

## GitHub Actions
The latest available retry of workflow run 3 (run ID `44078763134`, attempt 2) again completed with failure before any job steps were recorded. All four matrix jobs report no steps and no runner log URL. This is consistent with a runner/job provisioning failure, but the available API response does not expose a definitive root-cause message. The test source itself passed the fresh local checks above.

Run: https://github.com/ramysaid721-sudo/FlyBrain-Research-Platform/actions/runs/44078763134

## Scope and limitations
- No application source files were changed during this validation.
- No provider credentials, paid resources, deployments, or external scientific compute were activated.
- No claim is made that synthetic temporal/LIF models are biologically validated.
- GitHub Actions remains unresolved until GitHub exposes the runner provisioning error or the account/repository Actions configuration is corrected.
