# Final verification

This record separates actual external operations, offline execution and controlled inputs. No Bedrock request or deployment is performed during this final-evidence round. See [Source of Truth](FINAL_SUBMISSION_SOURCE_OF_TRUTH.md) for identity and scope.

## OFFLINE VERIFIED — current local checkpoint

Executed from the AWS checkout with Python 3.12.13; machine-specific dependency-cache prefix omitted:

```sh
uv run --offline --no-sync pytest -q
uv run --offline --no-sync ruff check src scripts tests/test_slice.py tests/test_web.py tests/test_profile_form.py
uv run --offline --no-sync python scripts/verify_manifest.py
uv build --offline
uv build packages/core --offline
```

Current test run: **90 passed, 1 skipped in 1.07s**. Lint: all checks passed. Core: 21 SHA-256 hashes match pin f269f7f3af4cf61f79771d63bcf3af0acf356955. The skipped test is `tests/test_slice.py::test_live_bedrock_saved_evidence`; paid opt-in is deliberately absent. Historical skip text says “not authorized,” but a separate bounded live run was authorized; this skip is not inference evidence.

Profile mapping coverage: exact browser control paths, existing Core types/enums, all exposed paths, null/false/zero, no nationality/adult/team-size inference, invalid/conflicting inputs, actual Fit inputs, residence blockers and no arbitrary scripted Fit. Existing saved example remains isolated. The final demo JSON is validated through the same adapter, with no new profile schema.

Package builds produce AWS/Core wheels and source distributions. Inspect archives for required licenses and Core/profile source, and absence of private state/evidence/cache/handoff/history. No distribution is uploaded to a package registry. Completed build inspection is recorded below; fresh-clone provenance is recorded in the publication section.

## CONTROLLED TEST — browser walkthrough

Use FINAL_DEMO_RUNBOOK Path B. Verify the fictional Taiwan builder → ineligible/not eligible/2 calls; saved Canadian fixture → uncertain/verify first/4 calls and verification plan; custom nonblocked profile → unavailable Fit/Plan/2 calls. Clear form → unknown; edited result invalidates. Watch sequence 1, 0, 1, 0, 0; failed retrieval preserves last baseline. All rules/drafts/controlled deadline changes are synthetic.

Exactly five real-UI captures are indexed in FINAL_SCREENSHOT_INDEX; architecture.svg is the actual local diagram. Browser logs, exact screenshot checksums and rehearsal observations are recorded below.

## LIVE VERIFIED — restricted external scope / BLOCKED inference

Historical actual HTTP retrieval of the official rules page succeeded; sanitized summary is `docs/test-results/retrieval-summary.json`. Historical temporary AWS login/STS/catalog succeeded. One actual Bedrock request was denied: `docs/live-status.json` preserves time/model/region/latency/error. Successful inference: none. AWS hosting/deployment: none. No retry until account condition changes; next model is in-region amazon.nova-lite-v1:0 in us-east-1. Never use successful retrieval, catalog, GitHub publication or local tests as a substitute for live inference.

## Reproducibility / public-file procedure

```sh
git clone https://github.com/hansonxdxd/prizehunter-aws.git
cd prizehunter-aws
uv sync --frozen --python 3.12
uv run --offline --no-sync pytest -q
uv run --offline --no-sync ruff check src scripts tests/test_slice.py tests/test_web.py tests/test_profile_form.py
uv run --offline --no-sync python scripts/verify_manifest.py
uv run --offline --no-sync python scripts/check_public_release.py --history
```

The repository includes packages/core and uses its relative path. Dependency-download caches may accelerate installs; no source imports come from a private reference checkout. The explicit public allowlist excludes internal handoffs, local paths, credentials and raw traces. Scans inspect recognized secret patterns and all reachable public content/commit objects; every selected file is reviewed. This is bounded pattern review, not a proof that every imaginable secret is detectable.

Internal reference verification compares read-only before/after HEAD, status, tracked hashes and file metadata for Google/NEXT. Existing Google demo_recordings is not created, deleted or edited by this task. Only AWS files are published; private lineage remains private.

## Completed local evidence / asset audit

All four distributions built successfully in this round: AWS wheel and sdist, standalone Core wheel and sdist. Archive inspection confirmed licenses and expected source, including profile_form.py in AWS packages, with no private state/cache/evidence/handoff/history. The in-source uv-cache warning did not correspond to cache content in the inspected archives.

Actual browser rehearsal completed with the documented fictional Taiwan profile (solo/1, skills, goals, travel false, hours 12 and region Taipei). Maximum travel days is blank/null as documented. Core produced the expected synthetic blocker and skipped inference. A separate one-click Canadian example produced uncertain/verify first/four scripted calls and verification plan. Blank/custom-zero-hours checks showed unavailable offline Fit/Plan; edited-result invalidation and reset recovery worked. Watch returned 1, 0, 1, 0, 0; a second step-1 reset restored one initial decision. Browser console warnings/errors: none.

Five captures are actual 1280×720 PNG files and were visually reviewed. The browser tool returned JPEG bytes; those captures were format-converted to PNG without changing layout or adding content. English architecture.svg matches the packaged SVG byte-for-byte. Captions in FINAL_SCREENSHOT_INDEX are each ≤140 characters. The 3:18 script contains approximately 375 spoken words; actual duration requires human rehearsal/recording. No video was recorded or submitted by this task.

| Screenshot | SHA-256 |
| --- | --- |
| 01_input.png | `1242fac5c2b52ebd4b0a35285885e34b872a4170ca4ceb024e24be0ad39444ef` |
| 02_offline_analysis.png | `2da14adf6db491dd3da521b76f40a1b88e1eee2d590464db5c5ca3fbf38c1130` |
| 03_evidence.png | `35342e455669e5159529c15cbb22b890e00eb5bb19e7bc1bb3aa12fc09f4c0bd` |
| 04_watch.png | `1126e453e52951df3d998d3ea43c93e58f9fabc5ac3259b7abf02adba74eb36a` |
| 05_architecture.png | `d4bf6406d22ae357a6ca527282ae85e2b4773937582467ae3368e29475a6782e` |

GitHub API confirmed the repository is public, main is its default branch and its detected license is MIT. This external verification is about publication, not AWS hosting.

Read-only reference before/after comparison passed for both projects: HEAD, Git status, tracked-file hashes and non-Git file metadata were unchanged. The existing Google demo_recordings directory was already present. No new Bedrock attempt was added; the ledger still contains exactly one historical denied request.
