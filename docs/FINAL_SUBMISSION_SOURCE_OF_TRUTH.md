# Final submission source of truth

Authoritative factual record for PrizeHunter AWS Edition. Prepared 2026-09-14 UTC. Other final documents derive from this record and the [claims matrix](FINAL_CLAIMS_MATRIX.md). Older milestone reports remain historical evidence. When evidence changes, update this record, the matrix and all affected narration/captions together.

## Project identity

| Field | Fact |
| --- | --- |
| Official project name | PrizeHunter |
| Edition / submission display name | PrizeHunter AWS Edition |
| Value proposition | Turn competition rules into an evidence-grounded decision and a plan you can review. |
| Intended track | Professional Agents — proposed fit for independent builders/makers; HUMAN CONFIRM final selection, not submitted yet |
| Public repository | https://github.com/hansonxdxd/prizehunter-aws |
| Exact public evidence checkpoint | `9cc2488c3a30e95ce10f75ddddd44555fc20b824`; previous code tested from `6f2b320696846622edae58c889efd15a0bbcb4ac` |
| Exact internal implementation checkpoint | `e9bbf0f6bdd48e509ec9ddd6df33bcdcb54fc807`; public code equivalent excludes private working history |
| Core pin | `f269f7f3af4cf61f79771d63bcf3af0acf356955`; 21 original file hashes unchanged |
| Current demo | Local OFFLINE VERIFIED / CONTROLLED TEST; Path B |

Professional Agents is an available track on the [official event overview](https://agentsforhumans.devpost.com/), checked 2026-09-14. The proposed track selection is our positioning, not organizer approval. Human must confirm final project title, track, team, Builder ID and eligibility. The same overview lists the deadline as September 14, 2026 at 17:00 PDT (September 15 at 08:00 Asia/Taipei); verify the submission portal before sending. Do not infer eligibility from this overview or the fictional profile.

## User / problem

Target user: an independent AI/product builder or small maker team deciding which competitions deserve limited build time. Rules, participant constraints, evidence and reuse restrictions are scattered; rereading unchanged opportunities wastes attention. This is the product hypothesis from earlier PrizeHunter work, not a newly measured time-saving or user-adoption result.

More than a conversational answer is needed: typed profile facts, preserved source evidence, deterministic eligibility gates, guarded recommendations and a remembered baseline make decisions auditable across repeated checks. No comparative chatbot benchmark or production outcome has been measured.

## Actual implemented workflow

Profile → approved/saved source evidence → one Strands Agent → structured ResearchDraft → CompetitionRecord + typed claims → literal evidence/claim validation → PrizeHunter Core → deterministic Eligibility → guarded Fit → Recommendation → Action Plan → local Opportunity Watch comparison → Human Review.

This describes the pipeline, not an assertion that every browser click runs all stages live. Three concrete paths exist:

1. **Custom Profile:** submitted fields map to existing Core contracts; two scripted research calls read synthetic Canada-only evidence. Entered facts reach Core Eligibility and Fit inputs. A hard blocker yields deterministic not_eligible/skipped planning. Otherwise Fit and Plan are null, explicitly unavailable offline; no example score is personalized.
2. **Saved synthetic example:** one click restores the original Canadian fixture; four scripted model calls exercise research/Fit/Plan through the real Strands SDK. Expected uncertain → verify_first → verification_first. This is not the user's or author's profile.
3. **Operator-only Bedrock path:** implemented and gated, but successful inference has not occurred. Real source retrieval separately succeeded. No replay fallback on live failure.

The Watch browser walkthrough is a separate saved baseline, not an automatic continuation for the edited custom profile. There is no background trigger. Current baseline is synthetic; an optional saved-live artifact loader exists but no such artifact is present.

## Profile

Progressive disclosure: essentials first; **Participation, travel & reusable work** expands preferences; **Advanced Eligibility** holds uncommon rule facts with nested entity/project sections. Fields derive types, enums, defaults and validation from Core JSON schemas via `profile_form.py`; no second profile schema or Core redesign.

| Browser field | Existing Core contract path | Primary role |
| --- | --- | --- |
| Country of residence | `UserProfile.country` | Eligibility |
| Citizenship | `UserProfile.citizenships` | Eligibility |
| Legal adult where you reside | `UserProfile.has_reached_age_of_majority` | Eligibility |
| Participant statuses | `UserProfile.entrant_statuses` | Eligibility |
| Team preference | `UserProfile.team_preference` | Fit / eligibility context; not actual team size |
| Intended team size | `UserProfile.intended_team_size` | Eligibility |
| Skills | `UserProfile.skills` | Fit |
| Technical capabilities | `UserProfile.technical_capability` | Fit |
| Willingness to learn new technology | `UserProfile.willingness_to_learn_new_tech` | Fit |
| Available hours before deadline | `FitPreferences.available_hours_before_deadline` | Fit; also UserProfile.available_time.total_hours_before_deadline |
| Willing to travel | `FitPreferences.willingness_to_travel` | Fit |
| Maximum travel days | `FitPreferences.maximum_travel_days` | Fit |
| Interests | `FitPreferences.interests` | Fit |
| Strategic goals | `FitPreferences.strategic_goals` | Fit |
| Reusable assets | `FitPreferences.reusable_assets` | Fit |
| Willing to build fresh | `FitPreferences.willingness_to_build_fresh` | Fit; not an existing-work eligibility fact |
| State / province / region | `UserProfile.region` | Advanced eligibility |
| Exact age | `UserProfile.age` | Advanced eligibility; does not infer adulthood |
| Permanent-resident countries | `UserProfile.permanent_resident_countries` | Advanced eligibility |
| Subject to U.S. sanctions / export controls | `UserProfile.subject_to_us_sanctions_or_export_controls` | Advanced eligibility |
| Education statuses | `UserProfile.education_statuses` | Advanced eligibility |
| Graduation date | `UserProfile.graduated_on` | Advanced eligibility |
| Registered legal entity | `UserProfile.entity_profile.registered_legal_entity` | Advanced eligibility / entity |
| Entity types | `UserProfile.entity_profile.entity_types` | Advanced eligibility / entity |
| Country of incorporation | `UserProfile.entity_profile.incorporation_country` | Advanced eligibility / entity |
| Incorporation date | `UserProfile.entity_profile.incorporated_on` | Advanced eligibility / entity |
| Primary business country | `UserProfile.entity_profile.primary_business_country` | Advanced eligibility / entity |
| Currently operating | `UserProfile.entity_profile.operating` | Advanced eligibility / entity |
| Qualifies as an SME | `UserProfile.entity_profile.qualifies_as_sme` | Advanced eligibility / entity |
| Submitting an existing project | `UserProfile.candidate_project.is_existing` | Advanced eligibility / project |
| Project start date | `UserProfile.candidate_project.started_on` | Advanced eligibility / project |
| Already publicly released | `UserProfile.candidate_project.publicly_released` | Advanced eligibility / project |
| Previously submitted | `UserProfile.candidate_project.previously_submitted` | Advanced eligibility / project |
| Will be materially modified | `UserProfile.candidate_project.will_be_materially_modified` | Advanced eligibility / project |

Blank optional facts remain null. Nullable checkbox/list fields with no selection mean unknown, not confirmed none. Core's nonnullable list defaults are empty lists; explicit unknown enums remain unknown. The transport retains false and zero (including zero available hours). Current browser form changes clear optional maximum travel days when travel is No; the demo leaves that field unknown. Residence does not imply citizenship, age does not infer legal adulthood, solo does not invent a team size, and total hours do not imply weekly hours. Entity/project details need their Core-required status fields; incomplete or contradictory combinations are rejected.

Hard eligibility depends on explicit applicable source rules and known profile facts; merely exposing a field does not mean the current fixture tests that rule. Travel, skills, goals, assets and available capacity primarily inform Fit. Preference to build fresh is distinct from factual existing-project eligibility. Not exposed: resume upload/parsing, account identity, persistent personal profile storage, discovery/search UI, preferred reward types, preferred participation modes, a separate solo_preference switch, weekly hours and free-form uncertainty arrays. Unexposed Core defaults are not invented answers.

## Agent

One `strands.Agent` per analysis; `strands-agents==1.55.1`. Sequential tool execution, no extra agents. Registered research tools: `read_evidence` and `search_opportunities`; the latter returns unavailable and is not operational discovery. Strands also uses generated structured-output tools to return typed drafts; these are not extra research capabilities.

`ReplayModel` emits scripted tool-use/response events, requiring an actual successful tool result. It proves orchestration/validation, not reasoning quality. `BedrockModel` is a separate adapter behind explicit paid configuration and approved STS account identity. Research tools close before downstream decision generation. Hard blockers skip Fit inference; not_eligible/skip recommendations skip planner inference. Custom offline profiles cannot consume saved Fit/Plan drafts.

Bounds: research tool calls ≤6, unique sources ≤4. General runtime ≤16 model calls; live harness lowers this to 8/analysis and the sprint ledger permits at most 3 attempts (1 used). Each SDK invocation: 6 turns, 60,000 total tokens, 16,000 output tokens, 90-second timeout. A before-call check enforces a 180-second overall budget; this is not a hard process kill at exactly 180 seconds. Bedrock response max_tokens=4,096. SDK retry strategy disabled; HTTP retries have separate limits.

## Evidence / provenance

Approved URLs/origins only; no arbitrary browser URL fetching. Retrieval rejects private/reserved DNS addresses, pins connections to verified public IPs while preserving TLS hostname checks, revalidates redirects and disallows HTTPS downgrade. Robots checks fail closed. One isolated retrieval process has a 25-second outer timeout; worker budget 22 seconds, ≤12 HTTP exchanges including robots/retries, ≤2 attempts/request, at most 4 fetch iterations. Response ≤2,000,000 bytes; extracted text 100–60,000 characters; unencrypted PDF 1–25 pages. Thin dynamic pages, unsupported/compressed content and retrieval failures stay explicit failures, not rule absence.

Evidence stores source URL, observed time, retrieval method/status and SHA-256. CompetitionRecord transport facts require literal source support. Claims cite source excerpts; unsupported excerpts are rejected, cross-source fabrication is not promoted, conflicting claims remain unresolved and missing facts remain unknown. A quote proves text support, not that a model interpreted the rule correctly. Untrusted page instructions cannot expand tool scope. Tests exercise these properties; current UI evidence is synthetic at example.com.

## Eligibility

Core V3 evaluates explicit participant/rule facts deterministically. A confirmed blocker wins over missing facts. Missing or conflicting requirements stay uncertain rather than eligible. The controlled Canada-only fixture blocks the fictional Taiwan resident; this is not a real-world Taiwan ban or an Agents for Humans eligibility decision. Changing citizenship cannot substitute for residence. The saved Canadian example remains uncertain because its rules/profile do not establish all required facts.

## Fit

For non-ineligible results with an inference provider, Core builds the Fit prompt from record, evidence, eligibility, actual UserProfile and FitPreferences. Draft references are validated with at most one corrective generation. Ineligible outputs are deterministic not_eligible and skip inference. Uncertain eligibility downgrades a proposed go to verify_first. Empty decision context caps confidence at 0.5 and prevents an unqualified go. Fit is not purely deterministic scoring. In this browser release arbitrary profiles have no offline decision provider: Fit/Plan are null unless a hard blocker supplies a deterministic skipped result. Only the saved example shows scripted Fit.

## Action Plan

Core checks competition/profile/version/eligibility consistency and validates source/input references. verify_first produces a verification-first plan; it cannot masquerade as a full execution plan. not_eligible and skip stop planner inference. Validated tasks are a checklist for a human, not tool execution. No application submission, registration, payment, organizer contact or notification occurs. When custom offline Fit is unavailable, no plan is fabricated.

## Opportunity Watch

`run_once` stores one goal/profile identity and per-competition successful baseline: record, evidence URL/hash/status, eligibility and recommendation. Comparing the same baseline produces no pending decision; a changed field produces one. Reset/first observation produces one new-opportunity decision. A deliberately changed deadline fixture produces one change, and repeating it produces zero. Any failed source preserves the last successful baseline and returns retrieval_failed with no new decision.

Browser sequence: **1, 0, 1, 0, 0**. Current file: `local-state/web/judge-watch.json` or a dedicated `PH_WEB_STATE_DIR`. Local JSON with temporary-file replacement and browser process lock; not distributed transactions. A different goal/profile requires a separate state file. Browser reset touches only its demo baseline. No recurring scheduler, notification delivery, broad discovery or cloud multi-user persistence. Pending decisions are not sent alerts. Changes in evidence hashes can produce a difference; this is not a proven semantic-change classifier.

## AWS / Strands state

| Stage | Actual state |
| --- | --- |
| Configuration | Previously verified AWS CLI 2.36.44 browser login with temporary credentials; STS identity succeeded; named profile prizehunter, initial region us-east-1 |
| Catalog | Nova Lite catalog previously verified ACTIVE and streaming-capable; catalog is not inference access |
| Real request | One Strands ConverseStream request on 2026-09-14T13:36:36.676891Z; historical model us.amazon.nova-lite-v1:0 / us-east-1 |
| Outcome | AccessDeniedException; new account verification pending; 2.058 seconds, zero tool calls, zero reported tokens |
| Successful inference | None; no real analyzed competition or sanitized saved-live result |
| Deployment / hosting | No AWS app resources or hosted endpoint; local loopback server only |
| This evidence round | No AWS calls or Bedrock retries; no evidence that account verification changed |
| Next permitted attempt | After actual status change: prizehunter / us-east-1 / in-region amazon.nova-lite-v1:0; keep ledger |

Source: [sanitized historical attempt](live-status.json). Token-based estimate USD 0 is not billing data. Do not use geographic us.amazon.nova-lite-v1:0 on the Free plan without separately verified support. The harness's attestation flags do not establish account/model availability. Toolkit/CLI setup is development tooling, not hosting, AgentCore deployment or inference success.

## Tests / public release

Current suite: **90 passed, 1 skipped**. This round's local run: 1.07 seconds; lint and 21 pins passed. The skipped paid live test has no opt-in in the offline suite; it is not a passed live test. [Final verification](FINAL_VERIFICATION.md) records exact fresh-clone/build/browser/scan results and scope. Public source contains the Core export and uv lockfile; no hidden reference-checkout dependency. Private git history, credentials, raw account/model traces, caches and internal handoffs are excluded via the explicit publication allowlist. Recognizable-secret scans supplement human review, not a guarantee against every possible secret.

MIT applies to author-owned code in this AWS distribution, including the authorized Core export. Root and package LICENSE files retain the grant; dependencies retain their own licenses and notices. No relicensing of Google/NEXT or third-party web content. Public repo and code are inspectable; no package-registry release or hosted application is claimed.

## Prior work

PRIOR: product research/problem framing, Google prototype, provider-neutral Core, schemas and compatibility fixtures where applicable. Core pin and original implementation provenance are recorded in SOURCE_MANIFEST and PRIOR_WORK.

NEW IN AWS EDITION: one-agent Strands implementation, structured-output adapter, gated Bedrock integration, bounded retrieval integration, local Opportunity Watch, AWS browser/profile/demo work, AWS-specific tests, packaging and submission materials. This is not clean-room, entirely new-from-zero or organizer-approved reuse. See [final disclosure](FINAL_PRIOR_WORK_DISCLOSURE.md).

## Material limitations

- No successful Bedrock analysis or AWS-hosted demo; browser buttons never call a paid model.
- Saved-live loader is implemented/tested with fixtures but unused; current UI has no saved-live analysis button. Path A is not recordable as-is.
- Replay verifies code paths, not arbitrary model quality or personalized preferences. Synthetic rules/profile are not real eligibility advice.
- Watch is manually invoked, local, single-goal and separate from custom-profile form; no delivered notifications or unattended monitoring.
- No discovery provider, resume ingestion, login/Cognito, multi-user persistence, scheduler or extra agents.
- Profile country inputs are literal text; unknowns, contradictions and missing official facts can prevent a decision. No comprehensive geographic alias normalization is promised.
- Literal support does not eliminate interpretation errors; official rules and human review remain necessary.
- Retrieval cannot handle every website/PDF and deliberately refuses unsafe/unsupported sources.
- Local server lacks production identity/operational controls; bounded requests are not a complete production security audit.
- No measured adoption, time saved, win-rate improvement, production reliability or organizer approval.
- Video, final Builder ID/team/track confirmation and Devpost submission remain human actions; no submission has been sent.
