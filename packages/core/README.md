# PrizeHunter Core

Reusable competition facts, source provenance, deterministic eligibility and
guarded Fit/Action Plan logic. Runtime dependencies: Python 3.11–3.13 and
Pydantic >=2.11,<3. No provider SDK, web framework or cloud credentials required.

From the repository root, install just Core into a chosen environment:

```sh
uv pip install --python /path/to/venv/bin/python ./packages/core
```

For the current Google application, `uv sync --frozen` installs this same package
as a workspace dependency. Do not copy its modules into another Edition.

## Minimal deterministic consumer

```python
from datetime import UTC, datetime
from prizehunter_core.schemas import CompetitionRecord
from prizehunter_core.user_profile import UserProfile
from prizehunter_core.eligibility_assessment_v3 import evaluate_eligibility_v3

record = CompetitionRecord(
    competition_name="Example competition",
    geographic_restrictions=["Open only to legal residents of Canada."],
)
profile = UserProfile(profile_id="personal", version=1, country="Taiwan")
assessment = evaluate_eligibility_v3(
    record, profile,
    competition_id="example",
    now=datetime(2026, 9, 8, tzinfo=UTC),
)
assert assessment.overall_status.value == "ineligible"
# Missing age/team/deadline facts stay in the nested uncertainty state.
```

A retrieval implementation supplies `CompetitionEvidenceBundle`, including
stable source IDs, exact text, hashes and failure statuses. A structured extractor
supplies `CompetitionRecord` and `EligibilityClaimBatch`; use
`validate_claim_drafts(...)` before consuming their typed claims. Rejected claims
and unresolved conflicts must remain visible.

## Structured decision seam

Both `evaluate_fit` and `plan_actions` require keyword arguments `generator` and
`model`. The generator is the existing small callable contract:

```python
def generator(prompt: str, response_schema: type):
    # Call your selected inference implementation, then return a Pydantic
    # response_schema instance or a schema-compatible structured mapping.
    # This callable is supplied by the consumer, not implemented by Core.
    return parsed_result, usage_or_none
```

The caller supplies the actual implementation of the example above. Core owns
source/input-reference validation, the single correction attempt, blocked-call
skipping, recommendation policy and final plan composition. A structured result
is untrusted until these checks pass. Usage never controls a business decision;
`None` is supported. For compatibility the optional usage aggregator understands
`prompt_token_count`, `candidates_token_count`, `total_token_count`,
`cached_content_token_count`, `thoughts_token_count` attributes and `call_count`.

Pass the same `CompetitionRecord`, `CompetitionIntelligence`, evidence,
`EligibilityAssessmentV3`, profile, preferences and explicit `generated_at` to
Fit. Pass its `FitEvaluation` plus uncertainty/conflict lists to planning.
Outputs use `inference_skipped`; evaluated outputs record the supplied model.
Plans are suggestions with human review, and cannot claim external execution.

Core functions do not retrieve URLs, create a model client, register or submit
anything. Google-compatible aliases and model-name checks live in `app`.
New consumers should import `prizehunter_core`, not compatibility modules.

See `docs/CORE_BOUNDARY.md`, `PORTABILITY_MATRIX.md` and
`docs/EXTRACTION_REPORT.md` in the repository for the complete contract map,
Google migration inventory, independent tests and known verification limits.
