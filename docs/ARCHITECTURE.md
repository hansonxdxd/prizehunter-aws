# Verified architecture

![Architecture](architecture.svg)

**OFFLINE VERIFIED, 2026-09-14.** The actual judge test build is a local Python web server plus one Strands agent, deterministic Core and local JSON Watch state. Scripted model responses are explicitly labeled synthetic replay. No AWS hosting or live Bedrock inference is claimed.

1. `web.py` serves packaged HTML/SVG and curated JSON routes. `profile_form.py` maps form transport values directly into existing Core `UserProfile` and `FitPreferences`, obtaining types/enums/defaults from Core. No second profile schema exists. Browser calls cannot invoke Bedrock.
2. `StrandsRuntime` uses one real `strands.Agent`, sequential tool execution, bounded invocation limits and strict structured-output validation.
3. `ResearchTools` reads allowlisted evidence. Live retrieval is isolated in a subprocess with DNS/IP, redirect, robots, time and size checks. Search returns unavailable.
4. The unchanged Core validates literal evidence and typed claims, resolves conflicts conservatively, assesses eligibility, gates Fit and composes a human-reviewed Action Plan.
5. `watch.run_once` stores a goal and successful opportunity snapshot in local JSON, compares meaningful fields, and suppresses repeats. A failed retrieval cannot replace the last good baseline.

Custom profiles use two scripted research calls against synthetic evidence. Core evaluates their real entered eligibility facts and receives their Fit inputs; when personalized inference is needed, Fit and Plan are explicitly unavailable. Only the one-click saved example uses four scripted research/Fit/Plan calls. Watch remains a separate saved-example walkthrough. See [Profile](PROFILE.md).

The separately implemented `BedrockModel` adapter is not part of the verified replay diagram. It requires an explicit paid-operation gate, approved account/region/model and successful STS identity check. Temporary login and STS identity verification succeeded. The first inference request was denied because AWS account verification is pending. If a reviewed saved live artifact is added later, the browser labels it **SAVED LIVE RESULT — no new model call**; that artifact does not exist in this release.

The controlled Watch changed-deadline fixture is a simulation, not a fresh organizer announcement. No scheduler or external notifications exist. This is a single-goal, sequential test build; local process locking is not a distributed state solution.

Author-owned existing Core/research is prior work. See [provenance](PRIOR_WORK.md).
