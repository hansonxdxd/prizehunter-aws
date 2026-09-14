# Final demo runbook

Recommended today: **PATH B**, OFFLINE VERIFIED / CONTROLLED TEST. Preserve the current Profile implementation. Do not improvise a successful live story. Pair with the [3:18 script](FINAL_DEMO_SCRIPT.md) and [five screenshot index](FINAL_SCREENSHOT_INDEX.md).

## Preconditions

```sh
git clone https://github.com/hansonxdxd/prizehunter-aws.git
cd prizehunter-aws
uv sync --frozen --python 3.12
uv run --no-sync python scripts/verify_manifest.py
PH_WEB_STATE_DIR=local-state/final-demo uv run --no-sync python -m prizehunter_aws.web --port 8080
```

Expected URL: **http://127.0.0.1:8080/**. Use one current desktop browser tab at 1280×720 or larger and normal zoom; close private account/terminal tabs before recording. If 8080 already runs this exact build, use it or stop only that process with Ctrl-C before restarting. Do not run another version on the same port. Browser cannot spend model credits. Expected current state: login previously verified, Bedrock account-verification blocker unresolved, no saved-live artifact or hosting.

Read `http://127.0.0.1:8080/health`: status ok, paid_browser_calls false. This health response is not Bedrock evidence. Confirm the visible OFFLINE VERIFIED badge, result-specific label and synthetic example.com source. Optional `GET /api/result` should report offline_synthetic_replay today; it does not run Bedrock.

## Demo dataset/profile

Use **Fictional Taiwan independent AI/product builder** as the main Profile story. All entries below are CONTROLLED TEST, including legal adulthood; they are not the author's verified private identity. No name, email, credentials, resume or personal document is used.

Exact transport values are in `examples/demo-taiwan-profile-form.json`. This is a fixture of the existing form transport, not a second profile schema. For recording, prefill the table before starting; briefly edit hours and expand preferences on camera. Fill citizenship and legal-adult status explicitly. All blank/empty rows remain unknown; do not fill them from assumptions.

| Browser field | Existing Core contract path | Fictional demo value |
| --- | --- | --- |
| Country of residence | `UserProfile.country` | Taiwan |
| Citizenship | `UserProfile.citizenships` | Taiwan |
| Legal adult where you reside | `UserProfile.has_reached_age_of_majority` | true |
| Participant statuses | `UserProfile.entrant_statuses` | professional, developer, individual |
| Team preference | `UserProfile.team_preference` | solo |
| Intended team size | `UserProfile.intended_team_size` | 1 |
| Skills | `UserProfile.skills` | Python, TypeScript, product design |
| Technical capabilities | `UserProfile.technical_capability` | AI agent prototypes, API integration, web applications |
| Willingness to learn new technology | `UserProfile.willingness_to_learn_new_tech` | high |
| Available hours before deadline | `FitPreferences.available_hours_before_deadline` | 12 |
| Willing to travel | `FitPreferences.willingness_to_travel` | false |
| Maximum travel days | `FitPreferences.maximum_travel_days` | Unknown / leave blank |
| Interests | `FitPreferences.interests` | AI agents, developer tools, productivity |
| Strategic goals | `FitPreferences.strategic_goals` | Build a credible portfolio, validate a useful product |
| Reusable assets | `FitPreferences.reusable_assets` | Generic prototype components, original product sketches |
| Willing to build fresh | `FitPreferences.willingness_to_build_fresh` | true |
| State / province / region | `UserProfile.region` | Taipei |
| Exact age | `UserProfile.age` | Unknown / leave blank |
| Permanent-resident countries | `UserProfile.permanent_resident_countries` | Unknown / leave blank |
| Subject to U.S. sanctions / export controls | `UserProfile.subject_to_us_sanctions_or_export_controls` | Unknown / leave blank |
| Education statuses | `UserProfile.education_statuses` | Unknown / leave blank |
| Graduation date | `UserProfile.graduated_on` | Unknown / leave blank |
| Registered legal entity | `UserProfile.entity_profile.registered_legal_entity` | Unknown / leave blank |
| Entity types | `UserProfile.entity_profile.entity_types` | Unknown / leave blank |
| Country of incorporation | `UserProfile.entity_profile.incorporation_country` | Unknown / leave blank |
| Incorporation date | `UserProfile.entity_profile.incorporated_on` | Unknown / leave blank |
| Primary business country | `UserProfile.entity_profile.primary_business_country` | Unknown / leave blank |
| Currently operating | `UserProfile.entity_profile.operating` | Unknown / leave blank |
| Qualifies as an SME | `UserProfile.entity_profile.qualifies_as_sme` | Unknown / leave blank |
| Submitting an existing project | `UserProfile.candidate_project.is_existing` | Unknown / leave blank |
| Project start date | `UserProfile.candidate_project.started_on` | Unknown / leave blank |
| Already publicly released | `UserProfile.candidate_project.publicly_released` | Unknown / leave blank |
| Previously submitted | `UserProfile.candidate_project.previously_submitted` | Unknown / leave blank |
| Will be materially modified | `UserProfile.candidate_project.will_be_materially_modified` | Unknown / leave blank |

With travel set to No, current form change events clear the optional maximum-travel-days field; leave it blank for this exact demo. Travel itself stays false.

Essentials are visible immediately. Expand **Participation, travel & reusable work** for team/travel/learning/assets. Advanced fields are in **Advanced Eligibility · only when a rule requires it**. The demo sets region only; all other Advanced fields stay blank. In the current synthetic rules this Taiwan residence must result in ineligible/not eligible with two research calls and skipped Fit/Planner. That is a demonstration of a fictitious Canada-only rule, not a conclusion about the real event.

## PATH A — Live Bedrock available (conditional, not currently recordable)

Do not select Path A merely because login, STS or catalog succeeds. Only after the account-verification condition actually changes may the operator run the existing bounded harness once:

```sh
AWS_PROFILE=prizehunter uv run --no-sync python scripts/live_validation.py --region us-east-1 --model amazon.nova-lite-v1:0 --account-verification-changed
```

Preserve the historical denied request and the 1/3 ledger. Do not reset attempts or use geographic `us.amazon.nova-lite-v1:0` without verified account support. Do not put credentials/account outputs in the recording. The existing harness uses its controlled Canadian goal; it does not read the edited browser form. A successful harness result cannot be relabeled as analysis of the fictional Taiwan profile.

Readiness gate: real Strands + Bedrock inference on official source must finish; validate excerpts/unknowns/Fit/Plan, sanitize and review a saved result, then verify Watch against that real baseline. Current `web.baseline()` can read a provenance-marked `assets/saved-live.json`, but **no such artifact exists and current browser buttons still request synthetic/custom-offline routes**. Do not manufacture this file or claim a current live button. Making a future verified saved result visibly selectable would require a small, separately tested demo integration and truthful Watch labels; record its exact button here before filming Path A.

Once those gates are actually completed, use this screen order: Profile (show the exact analyzed artifact's profile, not unrelated edits) → Analysis (select the newly verified saved-result display) → Evidence (real official URL/hash/time) → Eligibility → Fit → Action Plan → Opportunity Watch (real baseline, controlled change) → Architecture. Label saved output **SAVED LIVE RESULT — no new model call**. Outcomes depend on actual results; do not preselect eligible/go. A blocker skips inference, uncertain requires guarded recommendations, and failure sends recording back to Path B. **There is no executable current click sequence for live analysis; do not substitute a fictional control.**

## PATH B — Bedrock still blocked (executable now)

1. Start at the page top with the prepared fictional Taiwan profile. Show AWS Edition and OFFLINE VERIFIED. Use nav **Profile** if needed.
2. Show residence/citizenship/legal adult/statuses, skills and hours. Expand **Participation, travel & reusable work**; show solo/1, travel No, reusable assets and fresh-build Yes. Briefly expand Advanced and explain blank unknowns, then collapse it.
3. Click **Check my profile against demo rules**, then nav **Analysis**. Expect YOUR PROFILE / SYNTHETIC EVIDENCE, ineligible, not eligible, 2 Strands model calls and skipped downstream inference.
4. Nav **Evidence**. Read the source URL `https://example.com/synthetic-rules`, method offline-synthetic-v1 and the literal Canada-only rule. Explain this is fictitious evidence, not official event eligibility.
5. Nav **Profile**, click **Run saved synthetic example**, then nav **Analysis**. The form is overwritten with the separate Canadian fixture. Say aloud that this is a switch of dataset. Expect OFFLINE VERIFIED — saved synthetic example, uncertain, verify first, 4 scripted model calls and a verification action.
6. Show the Action Plan and expand **Uncertainty & rejected claims**, then **Execution evidence** if useful. Do not describe the recommendation as personalized for the Taiwan profile.
7. Optional rehearsal-only limitation check: edit Canadian hours to 0 and submit. Expect uncertain, Unavailable offline and 2 calls; no arbitrary Fit/Plan. Restore saved example afterwards. Do not add time to the 3:18 take.
8. Nav **Opportunity Watch** and run the exact sequence below. Its baseline is independent of the edited profile.
9. Nav **Architecture**. Show only the actual local components. Finish at public GitHub and testing record, then return to UI for closing.

## Opportunity Watch sequence / minimal reset support

The existing controls are sufficient; no reset script or product feature is added. Set a dedicated `PH_WEB_STATE_DIR` for recording. Never delete whole state directories or unrelated files.

| Step / exact button | Expected outcome |
| --- | --- |
| 1 · First observation / reset | Replaces only demo judge-watch.json with this baseline; changed, 1 decision; notifications sent 0 |
| 2 · Identical rerun | unchanged, 0 decisions |
| 3 · Simulate deadline change | changed, 1 decision; explicit CONTROLLED TEST |
| 4 · Repeat changed state | unchanged, 0 decisions |
| 5 · Simulate retrieval failure | retrieval_failed, 0 decisions; last successful baseline preserved |

To rehearse again, click step 1. It resets the on-screen Watch log and dedicated state, then creates the first decision; it is not a blank/delete-everything reset. **Run saved synthetic example** restores the known Canadian form/result. **Clear profile** resets form values to defaults/unknown and invalidates the old result; this does not delete Watch. Reloading clears transient form/log display but does not erase Watch state. Check mode/evidence labels again after every reset.

## Failure recovery

| Problem | Exact recovery |
| --- | --- |
| Server stops / connection refused | Restart the command above from the verified checkout; reload; restore profile or saved example; do not claim continuity of unsaved form data. |
| Port busy | Identify the known demo terminal and stop only that process, or use --port 8081 and update the recording URL. Do not kill unrelated processes. |
| Watch dirty / wrong order / profile mismatch | Click step 1 once, then 2–5 in order. Keep the dedicated demo state directory. |
| Section empty | Wait for the request to finish; read the form status message. Use the exact analyze/example button, then the matching nav link. If still empty, reload and inspect /health; do not record a fabricated result. |
| Profile validation error | Clear invalid/conflicting fields or use the exact table. Unknown is better than an invented answer. Entity/project details need their required status fact. |
| Old result appears faded / Not evaluated | The form was edited. Submit again or restore the saved example. Do not narrate the stale result as current. |
| Bedrock still blocked | Keep Path B, retain blocked historical record, and do not retry or enable paid tests. |
| Unexpected future saved-live state | Stop the take; verify artifact provenance and update all labels/runbook. Current Path B expects a synthetic Watch baseline. |
