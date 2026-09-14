# Final Devpost draft

Source copy, not a submitted entry. Factual authority: [Source of Truth](FINAL_SUBMISSION_SOURCE_OF_TRUTH.md) and [Claims Matrix](FINAL_CLAIMS_MATRIX.md). Bracketed claim IDs are editorial traceability notes; remove them when pasting only after human review. Current evidence mode is **OFFLINE VERIFIED / CONTROLLED TEST**; Bedrock and hosting remain unresolved.

**HUMAN CONFIRM before submission:** display name PrizeHunter AWS Edition; proposed Professional Agents track; final team/author details, AWS Builder ID, entrant eligibility and prior-work compliance; recorded video URL; any public demo URL (none exists); portal deadline and required fields. Do not insert invented values. No organizer approval, measured impact or successful live inference is asserted.

## Inspiration

Independent builders have limited time. An attractive competition may have a disqualifying rule, incompatible participation requirements or too much work before its deadline. Earlier PrizeHunter research and a Google-based prototype explored that decision problem. This edition carries forward that prior research and Core while building a Strands workflow around evidence, guarded decisions and a remembered baseline. [C22; Source: User/problem, Prior work]

## What it does

PrizeHunter AWS Edition turns competition rules into an evidence-grounded decision and a plan for human review. The browser collects residence, citizenship, participant facts and build preferences through progressive disclosure into the existing Core contracts. Missing facts stay unknown. Evidence retains source, time, hash and literal excerpts; Core checks eligibility before recommendations and planning. [C02–C04, C07, C09]

The current reproducible demo is explicitly offline. A fictional Taiwan builder is blocked by a fictitious Canada-only rule. A separate saved Canadian example demonstrates scripted Fit and a verification-first plan. Arbitrary edited profiles do not receive a fake personalized Fit result. Local Watch preserves a baseline, suppresses identical decisions and demonstrates a controlled deadline change and retrieval failure. No notifications are delivered. [C06, C08, C10–C12, C19, C23]

## How we built it

One real Strands Agent executes a sequential tool loop and returns structured drafts. Its bounded evidence tool reads approved sources or saved evidence; the search tool reports unavailable. The reused provider-neutral Core validates text support and claims, resolves uncertainty conservatively, evaluates eligibility and guards Fit and Action Plan outputs. Watch compares local JSON snapshots for one goal. Python serves a small local browser test build; source, lockfile and setup are public. [C01–C04, C07, C09, C11, C17, C21, C22]

A server-side Bedrock adapter and bounded harness are implemented. Temporary AWS login, STS and the Nova Lite catalog were verified. The first real Strands ConverseStream request was denied while AWS verified the new account. Successful Bedrock inference and AWS hosting remain unresolved; no live result is substituted with replay. [C13–C16]

## Challenges

The engineering challenge was keeping model drafts from bypassing source evidence and deterministic guards, while carrying real profile inputs into existing contracts. We also had to distinguish unknown facts from false or zero, keep changed form inputs from displaying stale recommendations, and preserve a Watch baseline when retrieval fails. Account verification blocked the live request, so the demo explicitly exposes its offline limits. [C02–C04, C07, C09, C11, C15]

## Accomplishments

The current suite passes 90 tests with one paid live test skipped. A fresh clone reproduces the build and HTTP profile/Watch workflow. The 21 pinned Core files remain unchanged. The browser demonstrates a real Strands tool loop with scripted outputs, eligibility blockers, honest unavailable-offline personalized Fit, and a controlled Watch sequence of 1, 0, 1, 0, 0. These are implementation and controlled-test results, not a model-quality or user-impact benchmark. [C01, C02, C06, C08, C12, C20–C22]

## What we learned

A useful decision workflow must distinguish missing facts, confirmed blockers and preferences. Source linkage and deterministic gates make generated drafts inspectable; a failed fetch should not erase a good baseline. Clear evidence labels are part of the product: scripted orchestration, a real external request and successful inference are different claims. [C03–C04, C07, C09, C11, C15]

## What's next

After AWS account verification actually changes, validate one bounded analysis with in-region Nova Lite in us-east-1, preserve and sanitize successful evidence, verify Watch against that baseline, then consider one minimal AWS host. Broader discovery, recurring monitoring and delivered notifications are not implemented or promised in this submission. [C15–C19, C24]

## Technologies used

Python, Strands Agents SDK, Pydantic, PrizeHunter Core, HTML/CSS/JavaScript, Beautiful Soup, pypdf, local JSON, pytest, Ruff, uv and GitHub. AWS integration: boto3/botocore, AWS CLI temporary browser login, STS; Amazon Bedrock adapter/request attempted, successful inference blocked. Do not tag AgentCore, Cognito or any hosting service as used. [C01, C13–C16, C20–C22; FINAL_ARCHITECTURE_AND_STACK]

## Testing instructions

Clone https://github.com/hansonxdxd/prizehunter-aws, run `uv sync --frozen --python 3.12`, then `uv run --no-sync pytest -q` and `uv run --no-sync python -m prizehunter_aws.web --port 8080`. Open http://127.0.0.1:8080/. No AWS credentials are needed for this test build. Use the fictional Taiwan profile from the runbook for the hard blocker, then **Run saved synthetic example** for scripted Fit/Plan. Run Watch buttons 1–5 in order. Expect 1, 0, 1, 0, 0, with no sent notifications. See FINAL_DEMO_RUNBOOK and FINAL_VERIFICATION for exact recovery and evidence. [C06, C08, C10, C12, C19–C21, C23]

## Prior Work Disclosure

PrizeHunter AWS Edition builds on earlier PrizeHunter research, a Google-based prototype and an existing provider-neutral Core, including schemas and compatibility fixtures. The AWS-specific work adds the Strands implementation, gated Bedrock integration, bounded retrieval, local Opportunity Watch, browser/profile work, tests and submission packaging. Core provenance is disclosed and its pinned files remain unchanged. This is not clean-room or entirely new-from-zero work; no organizer approval of reuse is claimed. MIT applies to author-owned code in this distribution; third-party notices remain. [C21–C22]
