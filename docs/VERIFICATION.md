# Verification record — 2026-09-14

## Verified release candidate

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

The public repository uses a fresh lineage. Private working commits, account identity output, OAuth data, model traces and internal Chinese handoffs are excluded. Source provenance remains in the README and manifest. A published-clone verification checkpoint will be recorded after the first public push.
