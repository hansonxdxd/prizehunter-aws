"""Adapter wiring; all business decisions are delegated to unmodified Core."""

import json
from datetime import UTC, datetime

from prizehunter_core import deadlines, expanded_eligibility
from prizehunter_core.action_planner import plan_actions
from prizehunter_core.competition_intelligence import ResolutionStatus
from prizehunter_core.eligibility_assessment_v3 import evaluate_eligibility_v3
from prizehunter_core.eligibility_claims import validate_claim_drafts
from prizehunter_core.evidence import CompetitionEvidenceBundle
from prizehunter_core.fit_evaluation import evaluate_fit

from .contracts import ResearchDraft
from .retrieval import canonical_url, origin, verify_bundle
from .runtime import ReplayModel


class OfflineDecisionUnavailable(RuntimeError):
    """The operator has no inference provider for arbitrary profile preferences."""


def unavailable_decision(prompt, schema):
    raise OfflineDecisionUnavailable(
        "Personalized Fit and planning require live inference; saved drafts are not personalized."
    )


def validate_record(record, bundle):
    """Reject ungrounded transport facts before any legacy fallback sees them."""
    successful = [s for s in bundle.sources if s.extraction_status.value == "success"]
    urls = {canonical_url(str(u)) for s in successful for u in [s.source_url, s.final_url] if u}
    if record.source_url and canonical_url(record.source_url) not in urls:
        raise ValueError("Record source_url was not successfully read")
    citations = {}
    for evidence in record.source_evidence:
        if evidence.field not in type(record).model_fields or not evidence.excerpt.strip():
            raise ValueError("Invalid record evidence field/excerpt")
        if not any(evidence.excerpt in (s.extracted_text or "") for s in successful):
            raise ValueError("Record evidence is not a literal source excerpt")
        citations.setdefault(evidence.field, []).append(evidence.excerpt)
    for field, value in record.model_dump().items():
        if field in {"source_url", "source_evidence", "uncertainties"} or value is None or value == []:
            continue
        for literal in value if isinstance(value, list) else [value]:
            if (
                not isinstance(literal, str)
                or not literal.strip()
                or not any(literal in q for q in citations.get(field, []))
            ):
                raise ValueError(f"Record {field} is not backed by literal field evidence")


def research_prompt(goal, urls):
    # Public Core contracts, no duplicated decision logic and no app initializer.
    names = [
        "ResidenceRequirement",
        "AgeRequirement",
        "TeamSizeRequirement",
        "CitizenshipRequirement",
        "EducationRequirement",
        "EntrantStatusRequirement",
        "EntityRequirement",
        "ExistingWorkRequirement",
    ]
    schemas = {name: getattr(expanded_eligibility, name).model_json_schema() for name in names}
    schemas["DeadlineValue"] = deadlines.DeadlineValue.model_json_schema()
    return (
        "Research these approved sources; read EVERY supplied source before completing the draft.\n"
        + json.dumps(
            {
                "goal": goal.model_dump(mode="json"),
                "approved_urls": urls,
                "claim_value_schemas": schemas,
                "claim_paths": [
                    "/deadline",
                    "/eligibility/residence",
                    "/eligibility/age",
                    "/eligibility/team_size",
                    "/eligibility/citizenship",
                    "/eligibility/education_status",
                    "/eligibility/entrant_status",
                    "/eligibility/entity",
                    "/eligibility/existing_work",
                ],
            },
            ensure_ascii=False,
        )
    )


def run_analysis(goal, urls, runtime, *, now=None, decision_generator=None):
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("Analysis time must have a timezone")
    if not 1 <= len(urls) <= 4:
        raise ValueError("Supply one to four known URLs/evidence sources")
    seed = canonical_url(urls[0])
    competition_id = seed
    started = datetime.now(UTC)
    draft, _ = runtime.generate(research_prompt(goal, urls), ResearchDraft)
    sources = sorted(runtime.tools.sources, key=lambda s: canonical_url(str(s.source_url)) != seed)
    if not sources or canonical_url(str(sources[0].source_url)) != seed:
        raise ValueError("Agent did not read the seed evidence")
    if {canonical_url(u) for u in urls} - {canonical_url(str(s.source_url)) for s in sources}:
        raise ValueError(
            "Agent did not read all supplied sources; cannot omit potential conflicting evidence"
        )
    payload = []
    for index, source in enumerate(sources):
        value = source.model_dump(mode="json")
        value["relation_to_seed"] = (
            "seed"
            if index == 0
            else ("same_origin" if origin(str(source.source_url)) == origin(seed) else "related_external")
        )
        payload.append(value)
    bundle = CompetitionEvidenceBundle.model_validate_json(
        json.dumps(
            {
                "seed_url": seed,
                "started_at": started.isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "sources": payload,
            }
        )
    )
    runtime.tools.closed = True
    verify_bundle(bundle)
    if not any(s.extraction_status.value == "success" for s in bundle.sources):
        raise ValueError("No usable evidence; eligibility remains unknown, not unrestricted")
    validate_record(draft.record, bundle)
    claims = validate_claim_drafts(draft.claims, bundle, competition_id=competition_id, observed_at=now)
    assessment = evaluate_eligibility_v3(
        draft.record, goal.profile, competition_id=competition_id, now=now, intelligence=claims.intelligence
    )
    arguments = {
        "competition_id": competition_id,
        "record": draft.record,
        "intelligence": claims.intelligence,
        "evidence_bundle": bundle,
        "eligibility": assessment,
        "profile": goal.profile,
        "preferences": goal.preferences,
        "generated_at": now,
        "generator": decision_generator or runtime.generate,
        "model": runtime.model_id,
    }
    decision_limitation = None
    try:
        fit, _ = evaluate_fit(**arguments)
    except OfflineDecisionUnavailable as exc:
        fit = None
        decision_limitation = str(exc)
    conflicts = [
        f.field_path
        for f in claims.intelligence.resolved_fields
        if f.resolution_status is ResolutionStatus.UNRESOLVED_CONFLICT
    ]
    plan = None
    if fit is not None:
        plan, _ = plan_actions(
            **arguments,
            fit=fit,
            model_uncertainties=claims.model_uncertainties,
            unresolved_conflicts=conflicts,
        )
    return {
        "mode": "offline_synthetic_replay" if isinstance(runtime.model, ReplayModel) else "live_bedrock",
        "competition_id": competition_id,
        "goal": goal.model_dump(mode="json"),
        "record": draft.record.model_dump(mode="json"),
        "evidence": bundle.model_dump(mode="json"),
        "claims": claims.model_dump(mode="json"),
        "eligibility": assessment.model_dump(mode="json"),
        "fit": fit.model_dump(mode="json") if fit is not None else None,
        "plan": plan.model_dump(mode="json") if plan is not None else None,
        "decision_limitation": decision_limitation,
        "execution": {
            "agent_instances": 1,
            "model_calls": runtime.budget.calls,
            "stages": runtime.stages,
            "tools": runtime.tools.events,
            "live_model": not isinstance(runtime.model, ReplayModel),
            "live_search": False,
            "external_actions_executed": False,
        },
    }
