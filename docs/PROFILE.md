# Profile experience

The AWS browser restores the prior PrizeHunter profile interaction pattern: essentials first, participation/build preferences on demand, and uncommon hard-rule facts under **Advanced Eligibility**. The Google submission was inspected read-only for interaction ideas; its defaults, discovery and local-storage behavior were not copied into this test build.

The form maps directly to **the existing `prizehunter_core.UserProfile` and `FitPreferences` contracts**. `profile_form.py` is a transport adapter: field types, defaults, enumerations and validation constraints are read from the Core JSON schemas. There is no new profile model or fork of Core business rules.

| Browser field | Existing Core field |
| --- | --- |
| Country of residence | `UserProfile.country` |
| Citizenship | `UserProfile.citizenships` |
| Legal adult | `UserProfile.has_reached_age_of_majority` |
| Participant statuses | `UserProfile.entrant_statuses` |
| Team preference / intended size | `team_preference` / `intended_team_size` |
| Skills / technical capabilities | `skills` / `technical_capability` |
| Available hours before deadline | `available_time.total_hours_before_deadline` and `FitPreferences.available_hours_before_deadline` |
| Travel / maximum days | `FitPreferences.willingness_to_travel` / `maximum_travel_days` |
| Interests / strategic goals | `FitPreferences.interests` / `strategic_goals` |
| Reusable assets / fresh build | `FitPreferences.reusable_assets` / `willingness_to_build_fresh` |
| Advanced eligibility | Region, exact age, permanent residence, sanctions/export status, education/graduation, entity facts and candidate-project facts in `UserProfile` |

Blank optional facts remain null. An empty participant/citizenship selection is unknown. Core's nonnullable list defaults remain empty lists, and its explicit `unknown` enums stay unknown. Residence never implies citizenship, age never implies legal adulthood, solo preference never supplies a team size, and total hours never implies weekly availability. Explicit false and zero remain false and zero.

## Actual analysis boundary

**Check my profile against demo rules** submits your form to the local server. The same Strands research replay reads the synthetic Canada-only evidence; the resulting record/claims are validated and Core evaluates eligibility using your actual entered profile. The exact `UserProfile` and `FitPreferences` objects also reach Core's `evaluate_fit` input boundary.

If Core identifies a hard blocker, its deterministic `not_eligible` and skipped-plan outputs are shown. Otherwise the inference adapter explicitly reports unavailable: **Fit and Plan are null**, with no synthetic score, recommendation or action plan substituted for the user's preferences. There are two research replay calls and no paid model call. This does not claim eligibility for a real competition or personalized model quality.

**Run saved synthetic example** restores the original Canadian example with one click and runs its four-call scripted research/Fit/Plan demonstration. Edits invalidate the visible result until checked again. The Watch walkthrough always uses its separately labeled saved example; it does not persist your custom profile or claim to monitor it.

The expandable **Profile & preferences sent to Core** panel shows validated inputs. Custom forms are not saved to disk or browser storage, and the browser cannot call Bedrock. Resume upload and search/discovery are not added.

## Verification

Tests cover all exposed fields, null/false/zero preservation, strict Core rejection, unsupported fields/enums, actual Core Fit inputs, residence-driven eligibility changes, no fabricated arbitrary Fit, unchanged saved examples, and form-control/contract path coverage. Separate tests verify in-region Nova Lite defaults and reject geographic cross-region use or unresolved account-denied retries before resolving credentials.
