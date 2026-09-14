# Verification record — 2026-09-14

Historical milestone record. The current final package is documented in [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md); current screenshots and narration use the FINAL documents.

## Profile restoration checkpoint

The browser now accepts the user's profile through the existing Core contracts. The restored essentials and expandable participation/Advanced Eligibility form has no second domain schema. **90 passed, 1 skipped** (0.99 seconds) in the working checkout; lint and all 21 pinned Core hashes passed. AWS and Core wheel/source distributions built; archive inspection confirmed licenses, the new profile transport module in AWS packages, and no private caches, state, evidence or handoffs.

```sh
uv run --offline --no-sync pytest -q
uv run --offline --no-sync ruff check src scripts tests/test_slice.py tests/test_web.py tests/test_profile_form.py
uv run --offline --no-sync python scripts/verify_manifest.py
uv build --offline
uv build packages/core --offline
```

Actual browser checks verified blank → unknown, false/zero preservation, custom preferences reaching Core, edited-result invalidation, residence-driven hard blockers, and the one-click saved example. Custom nonblocked profiles have null Fit/Plan and two research replay calls; the saved synthetic example retains four calls. The independent Watch walkthrough returned 1, 0, 1, 0, 0. No browser console errors/warnings appeared. Exactly five screenshots were refreshed from the working application.

**No AWS requests were made during Profile restoration.** The ledger remains at one historical denied request. The next default is in-region `amazon.nova-lite-v1:0` in `us-east-1`, after an actual account-verification change. Unit tests use mocks to verify the model default and pre-credential retry/cross-region guards; they do not establish AWS availability.

## Published Profile clone verification

A fresh GitHub clone resolved to **`6f2b320696846622edae58c889efd15a0bbcb4ac`**, matching the reviewed public candidate. A new Python 3.12.13 virtual environment was installed with `uv sync --frozen --offline --python 3.12`, using the existing dependency-download cache. There is no reference-checkout dependency. The test/lint/manifest commands above ran from that clone: **90 passed, 1 skipped** (3.67 seconds), lint passed, and all 21 Core hashes matched. The separate public candidate also passed 90/1 (1.24 seconds).

A temporary loopback HTTP server from the fresh clone verified health, Core enum options, custom country/skills/zero hours/false travel inputs, blank unknowns, residence blockers, unavailable arbitrary Fit/Plan, the four-call saved example, HTTP 400 for invalid hours and Watch counts 1, 0, 1, 0, 0. Both application and Core imports resolved inside the fresh clone. The temporary server was stopped afterwards.

The pre-push scan covered **72 allowlisted files and 92 reachable content/commit objects**, with no findings. This subsequent documentation-only checkpoint records those results; application source and lockfile remain the verified versions.

## Previous release candidate (before Profile restoration)

A separate directory was created using `scripts/export_public.py` and the reviewed allowlist. Its virtual environment was created from scratch. Installation uses the included `packages/core`; neither private reference checkout is required. Network access to PyPI was allowed for build dependencies; a local uv cache accelerated downloads but was not a source-code dependency.

Commands below were executed in that candidate (only the machine-specific `UV_CACHE_DIR` prefix is omitted):

```sh
uv sync --frozen --python 3.12
uv run --offline --no-sync pytest -ra
uv run --offline --no-sync ruff check src scripts tests/test_slice.py tests/test_web.py
uv build --offline
uv build packages/core --offline
```

| Check | Actual result |
| --- | --- |
| Fresh candidate install | Successful, Python 3.12.13, locked dependencies |
| Full offline tests | **67 passed, 1 skipped** (3.69 seconds) |
| Lint | All checks passed |
| AWS package | Wheel and source distribution built successfully |
| Core package | Wheel and source distribution built successfully |
| Core pin | 21 unchanged SHA-256 hashes match source manifest |
| Public candidate scan | Recognizable credential/private-path patterns: no findings |
| Browser analysis | Uncertain / verify first; four scripted Strands calls |
| Synthetic hard blocker | Ineligible / not eligible; two scripted Strands calls; Fit/Planner skipped |
| Browser Watch sequence | **1, 0, 1, 0, 0**; last good baseline preserved after retrieval failure |
| Fresh judge browser tab | No console warnings or errors during the full analysis/Watch walkthrough |
| Screenshot count | Exactly five, all captured from the actual local application |
| Bedrock live | **Blocked**: one real ConverseStream request denied pending AWS account verification |
| AWS deployment | No resources created; no hosted endpoint |

The skipped test checks the separate explicitly gated paid live path. Its historical skip message says “not authorized”; in this offline suite the opt-in flag is unset deliberately. The user did authorize a separate bounded live attempt, documented in [live status](live-status.json). No live pass is inferred from the skip.

Package inspection checks for `.venv`, caches, local state/evidence, internal handoffs and private Git history. The AWS sdist explicitly includes the pinned Core and necessary runtime/test files. MIT is included in both AWS and standalone Core artifacts. No distribution is uploaded to a package registry.

An initial install attempt inside a network-restricted runner failed fetching `hatchling`; allowing the already-authorized PyPI access resolved it. A browser inspection tab produced three `animation` TypeErrors during SVG/automation operations; their origin was not established. A fresh application-only judge tab repeated the complete workflow without warnings or errors. Neither incident is counted as a passing live AWS run.

## Public file/history procedure

`docs/PUBLICATION_CANDIDATES.json` is the explicit public allowlist. Every exported file is reviewed; binary screenshots are visually inspected. `scripts/check_public_release.py` scans all allowlisted bytes and, with `--history`, all reachable blobs/commits/tags plus exact tracked-file membership. The checks supplement review; they are not a mathematical guarantee that arbitrary secrets cannot exist. Third-party author/copyright notices are retained.

The public repository uses a fresh lineage. Private working commits, account identity output, OAuth data, model traces and internal Chinese handoffs are excluded. Source provenance remains in the README and manifest. The public repository was created and verified as PUBLIC at https://github.com/hansonxdxd/prizehunter-aws .

## Previous published-clone verification (before Profile restoration)

A fresh `git clone https://github.com/hansonxdxd/prizehunter-aws.git` resolved to `d9b75ea6c2f97a89ee78056e4ddc8e6eb15307ab`, exactly matching the reviewed public candidate. A new virtual environment was created from the lockfile. Commands:

```sh
uv sync --frozen --python 3.12
uv run --offline --no-sync pytest -ra
uv run --offline --no-sync ruff check src scripts tests/test_slice.py tests/test_web.py
uv run --offline --no-sync python scripts/verify_manifest.py
uv run --offline --no-sync prizehunter demo --output local-state/demo.json
```

Results: **67 passed, 1 skipped** (3.89 seconds); lint passed; all 21 pinned hashes matched. The CLI returned `offline_synthetic_replay`, `uncertain`, `verify_first`, `verification_first`, with four model calls.

A temporary HTTP server was then started from that fresh clone on port 8091. `/health` reported `ok` and disabled paid browser calls; `/api/result` returned the replay analysis; `/api/watch` returned counts **1, 0, 1, 0, 0** and preserved the last good baseline on failure. Both AWS application and Core imports resolved inside the new clone. The temporary server was stopped after verification.

The following publication checkpoint adds only this verification record; application source and lockfile remain the tested versions. Initial public history scan covered **69 tracked files and 68 unique reachable content/commit objects**, with no findings.
