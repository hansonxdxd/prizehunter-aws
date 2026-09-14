"""Traceable Decision-to-Action planning after eligibility and Fit."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from types import SimpleNamespace
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from prizehunter_core.competition_intelligence import CompetitionIntelligence, ResolutionStatus
from prizehunter_core.deadlines import DeadlineType, DeadlineValue
from prizehunter_core.eligibility_assessment_v3 import EligibilityAssessmentV3
from prizehunter_core.evidence import CompetitionEvidenceBundle, EvidenceExtractionStatus
from prizehunter_core.fit_evaluation import (
    CompetitionEvidenceReference,
    FitEvaluation,
    FitPreferences,
    FitRecommendation,
)
from prizehunter_core.evidence_formatting import format_evidence_for_model
from prizehunter_core.schemas import CompetitionRecord
from prizehunter_core.user_profile import UserProfile


class ActionPlanStatus(StrEnum):
    FULL = "full"
    VERIFICATION_FIRST = "verification_first"
    EXPLORATION = "exploration"
    SKIPPED = "skipped"


class ActionType(StrEnum):
    VERIFICATION = "verification"
    DECISION = "decision"
    PREPARATION = "preparation"
    SUBMISSION = "submission"
    MANDATORY_EVENT = "mandatory_event"


class ActionBasis(StrEnum):
    CONFIRMED_REQUIREMENT = "confirmed_requirement"
    AI_SUGGESTION = "ai_suggestion"
    VERIFICATION = "verification"


class ActionPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionStatus(StrEnum):
    NOT_STARTED = "not_started"
    BLOCKED_PENDING_VERIFICATION = "blocked_pending_verification"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class EffortRelationship(StrEnum):
    ALIGNED_WITH_FIT = "aligned_with_fit"
    UPDATED_FROM_DECOMPOSITION = "updated_from_decomposition"
    LIMITED_SCOPE = "limited_scope"
    UNKNOWN = "unknown"


class ActionInputReference(StrEnum):
    """Approved planner context keys; never free-form model pointers."""

    ELIGIBILITY_STATUS = "eligibility_status"
    ELIGIBILITY_BLOCKERS = "eligibility_blockers"
    ELIGIBILITY_UNCERTAINTIES = "eligibility_uncertainties"
    MODEL_UNCERTAINTIES = "model_uncertainties"
    SOURCE_CONFLICTS = "source_conflicts"
    SOURCE_FAILURES = "source_failures"
    FIT_RECOMMENDATION = "fit_recommendation"
    FIT_EFFORT = "fit_effort"
    FIT_RISKS = "fit_risks"
    FIT_UNCERTAINTIES = "fit_uncertainties"
    PROFILE_AVAILABLE_TIME = "profile_available_time"
    PREFERENCES_AVAILABLE_HOURS = "preferences_available_hours"
    PREFERENCES_GOALS = "preferences_goals"
    PREFERENCES_REUSABLE_ASSETS = "preferences_reusable_assets"


_ACTION_INPUT_POINTERS = {
    ActionInputReference.ELIGIBILITY_STATUS: "/eligibility/overall_status",
    ActionInputReference.ELIGIBILITY_BLOCKERS: "/eligibility/confirmed_blockers",
    ActionInputReference.ELIGIBILITY_UNCERTAINTIES: "/eligibility/uncertainties",
    ActionInputReference.MODEL_UNCERTAINTIES: "/model_uncertainties",
    ActionInputReference.SOURCE_CONFLICTS: "/unresolved_conflicts",
    ActionInputReference.SOURCE_FAILURES: "/source_failures",
    ActionInputReference.FIT_RECOMMENDATION: "/fit/recommendation",
    ActionInputReference.FIT_EFFORT: "/fit/effort_estimate",
    ActionInputReference.FIT_RISKS: "/fit/risks",
    ActionInputReference.FIT_UNCERTAINTIES: "/fit/uncertainties",
    ActionInputReference.PROFILE_AVAILABLE_TIME: "/profile/available_time",
    ActionInputReference.PREFERENCES_AVAILABLE_HOURS: (
        "/preferences/available_hours_before_deadline"
    ),
    ActionInputReference.PREFERENCES_GOALS: "/preferences/strategic_goals",
    ActionInputReference.PREFERENCES_REUSABLE_ASSETS: "/preferences/reusable_assets",
}


class ActionEffort(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    minimum_hours: float = Field(ge=0)
    maximum_hours: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.minimum_hours > self.maximum_hours:
            raise ValueError("Action effort minimum cannot exceed maximum.")
        return self


class ActionDeadline(BaseModel):
    """Organizer deadline; suggested timing belongs on the action instead."""

    model_config = ConfigDict(extra="forbid", strict=True)

    value: DeadlineValue
    competition_evidence: list[CompetitionEvidenceReference] = Field(min_length=1)


class ActionEvidenceDraft(BaseModel):
    """Compact structured response shape; converted to the shared evidence contract."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source_id: str = Field(alias="source", min_length=1)
    excerpt: str = Field(alias="quote", min_length=1)

    def to_reference(self) -> CompetitionEvidenceReference:
        return CompetitionEvidenceReference(
            source_id=self.source_id,
            excerpt=self.excerpt,
        )


class ActionItemDraft(BaseModel):
    """Model-produced task before deterministic status and policy composition."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    action_id: str = Field(alias="id", min_length=1)
    title: str = Field(min_length=1)
    short_reason: str = Field(alias="reason", min_length=1)
    action_type: ActionType = Field(alias="kind")
    basis: ActionBasis
    priority: ActionPriority
    estimated_effort: ActionEffort = Field(alias="effort")
    suggested_timing: str = Field(alias="timing", min_length=1)
    competition_evidence: list[ActionEvidenceDraft] = Field(alias="evidence")
    input_refs: list[str] = Field(alias="refs")
    dependency_ids: list[str] = Field(alias="depends_on")
    requires_human_confirmation: bool = Field(alias="human_confirmation")
    uncertainty: str
    confirmation_target: str = Field(alias="confirm_at")

    @field_validator("action_id")
    @classmethod
    def validate_action_id(cls, value: str) -> str:
        if re.fullmatch(r"action_[a-z0-9_]+", value) is None:
            raise ValueError("Action IDs must match action_[a-z0-9_]+.")
        return value

    @model_validator(mode="after")
    def validate_local_lengths(self) -> Self:
        limits = {
            "title": (self.title, 120),
            "reason": (self.short_reason, 500),
            "timing": (self.suggested_timing, 120),
            "uncertainty": (self.uncertainty, 500),
            "confirm_at": (self.confirmation_target, 300),
        }
        for label, (value, limit) in limits.items():
            if len(value) > limit:
                raise ValueError(f"{label} cannot exceed {limit} characters.")
        return self

    @model_validator(mode="after")
    def validate_basis(self) -> Self:
        if (
            self.basis is ActionBasis.CONFIRMED_REQUIREMENT
            and not self.competition_evidence
        ):
            raise ValueError("Confirmed organizer requirements require evidence.")
        if not self.competition_evidence and not self.input_refs:
            raise ValueError(
                "Every action needs evidence or a validated input reference."
            )
        if self.basis is ActionBasis.VERIFICATION:
            if self.action_type is not ActionType.VERIFICATION:
                raise ValueError(
                    "Verification basis requires verification action type."
                )
            if not self.uncertainty or not self.confirmation_target:
                raise ValueError(
                    "Verification actions require uncertainty and confirmation target."
                )
            if not self.requires_human_confirmation:
                raise ValueError("Verification actions require human confirmation.")
        if self.action_type in {ActionType.SUBMISSION, ActionType.MANDATORY_EVENT}:
            if not self.requires_human_confirmation:
                raise ValueError(
                    "Submission and mandatory-event actions require human confirmation."
                )
        if len(self.dependency_ids) != len(set(self.dependency_ids)):
            raise ValueError("Action dependencies cannot contain duplicates.")
        if self.action_id in self.dependency_ids:
            raise ValueError("An action cannot depend on itself.")
        return self


class ActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=120)
    short_reason: str = Field(min_length=1, max_length=500)
    action_type: ActionType
    basis: ActionBasis
    priority: ActionPriority
    estimated_effort: ActionEffort
    deadline: ActionDeadline | None = None
    suggested_timing: str | None = Field(default=None, min_length=1, max_length=120)
    competition_evidence: list[CompetitionEvidenceReference] = Field(
        default_factory=list
    )
    input_refs: list[ActionInputReference] = Field(default_factory=list)
    dependency_ids: list[str] = Field(default_factory=list)
    requires_human_confirmation: bool
    uncertainty: str | None = Field(default=None, min_length=1, max_length=500)
    confirmation_target: str | None = Field(default=None, min_length=1, max_length=300)
    confirmation_target_source_id: str | None = Field(default=None, min_length=1)
    status: ActionStatus

    @model_validator(mode="after")
    def validate_basis(self) -> Self:
        if (
            self.basis is ActionBasis.CONFIRMED_REQUIREMENT
            and not self.competition_evidence
        ):
            raise ValueError("Confirmed organizer requirements require evidence.")
        if not self.competition_evidence and not self.input_refs:
            raise ValueError(
                "Every action needs evidence or a validated input reference."
            )
        if self.basis is ActionBasis.VERIFICATION:
            if self.action_type is not ActionType.VERIFICATION:
                raise ValueError(
                    "Verification basis requires verification action type."
                )
            if not self.uncertainty or not self.confirmation_target:
                raise ValueError(
                    "Verification actions require uncertainty and confirmation target."
                )
            if not self.requires_human_confirmation:
                raise ValueError("Verification actions require human confirmation.")
        if self.action_type in {ActionType.SUBMISSION, ActionType.MANDATORY_EVENT}:
            if not self.requires_human_confirmation:
                raise ValueError(
                    "Submission and mandatory-event actions require human confirmation."
                )
        if len(self.dependency_ids) != len(set(self.dependency_ids)):
            raise ValueError("Action dependencies cannot contain duplicates.")
        if self.action_id in self.dependency_ids:
            raise ValueError("An action cannot depend on itself.")
        return self


class ActionPlanDraft(BaseModel):
    """Untrusted structured task decomposition from inference."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    overall_objective: str = Field(alias="objective", min_length=1)
    actions: list[ActionItemDraft] = Field(min_length=1)
    suggested_sequence: list[str] = Field(alias="sequence", min_length=1)
    unresolved_items: list[str] = Field(alias="unresolved")

    @model_validator(mode="after")
    def validate_local_objective_length(self) -> Self:
        if len(self.overall_objective) > 500:
            raise ValueError("objective cannot exceed 500 characters.")
        if len(self.actions) > 15:
            raise ValueError("actions cannot contain more than 15 items.")
        return self


class PlanEffortSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    plan_minimum_hours: float = Field(ge=0)
    plan_maximum_hours: float = Field(ge=0)
    fit_minimum_hours: float | None = Field(default=None, ge=0)
    fit_maximum_hours: float | None = Field(default=None, ge=0)
    relationship: EffortRelationship
    note: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if self.plan_minimum_hours > self.plan_maximum_hours:
            raise ValueError("Plan effort minimum cannot exceed maximum.")
        if (self.fit_minimum_hours is None) != (self.fit_maximum_hours is None):
            raise ValueError("Fit effort reference requires both bounds or neither.")
        if (
            self.fit_minimum_hours is not None
            and self.fit_maximum_hours is not None
            and self.fit_minimum_hours > self.fit_maximum_hours
        ):
            raise ValueError("Fit effort minimum cannot exceed maximum.")
        return self


class ActionPlan(BaseModel):
    """UI-ready checklist that never executes an external action."""

    model_config = ConfigDict(extra="forbid", strict=True)

    plan_version: Literal["1.0"] = "1.0"
    plan_status: ActionPlanStatus
    competition_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_version: int = Field(ge=1)
    fit_evaluation_version: str = Field(min_length=1)
    recommendation_reference: FitRecommendation
    generated_at: datetime
    overall_objective: str = Field(min_length=1)
    actions: list[ActionItem] = Field(default_factory=list)
    suggested_sequence: list[str] = Field(default_factory=list)
    estimated_total_effort: PlanEffortSummary | None = None
    unresolved_items: list[str] = Field(default_factory=list)
    stopped_reasons: list[str] = Field(default_factory=list)
    execution_policy: Literal["suggestion_only_human_approval_required"] = (
        "suggestion_only_human_approval_required"
    )
    external_actions_executed: Literal[False] = False
    model: str | None = None
    inference_skipped: bool = False
    skip_reason: str | None = None

    @model_validator(mode="after")
    def validate_plan_policy(self) -> Self:
        skipped_recommendations = {
            FitRecommendation.NOT_ELIGIBLE,
            FitRecommendation.SKIP,
        }
        if self.recommendation_reference in skipped_recommendations:
            if self.plan_status is not ActionPlanStatus.SKIPPED:
                raise ValueError("NOT_ELIGIBLE and SKIP require a skipped plan.")
            if not self.inference_skipped or self.model is not None:
                raise ValueError("Skipped plans must not use inference.")
            if self.actions or self.suggested_sequence or self.estimated_total_effort:
                raise ValueError("Skipped plans cannot contain execution tasks.")
            if not self.stopped_reasons:
                raise ValueError("Skipped plans require a stopped reason.")
            return self

        if self.inference_skipped or not self.model:
            raise ValueError("Actionable plans must record the configured model.")
        if not self.actions or self.estimated_total_effort is None:
            raise ValueError("Actionable plans require actions and effort summary.")
        if self.stopped_reasons:
            raise ValueError("Actionable plans cannot contain stopped reasons.")

        action_ids = [action.action_id for action in self.actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("Action IDs must be unique.")
        if self.suggested_sequence != list(dict.fromkeys(self.suggested_sequence)):
            raise ValueError("Suggested sequence cannot contain duplicates.")
        if set(self.suggested_sequence) != set(action_ids):
            raise ValueError(
                "Suggested sequence must contain every action exactly once."
            )
        positions = {
            action_id: index for index, action_id in enumerate(self.suggested_sequence)
        }
        for action in self.actions:
            for dependency in action.dependency_ids:
                if dependency not in positions:
                    raise ValueError(f"Unknown action dependency: {dependency}")
                if positions[dependency] >= positions[action.action_id]:
                    raise ValueError("Dependencies must precede dependent actions.")

        if self.recommendation_reference is FitRecommendation.VERIFY_FIRST:
            if self.plan_status is not ActionPlanStatus.VERIFICATION_FIRST:
                raise ValueError(
                    "VERIFY_FIRST requires verification-first plan status."
                )
            first = next(
                action
                for action in self.actions
                if action.action_id == self.suggested_sequence[0]
            )
            if first.action_type is not ActionType.VERIFICATION:
                raise ValueError("VERIFY_FIRST must begin with a verification task.")
        elif self.recommendation_reference is FitRecommendation.MAYBE:
            if self.plan_status is not ActionPlanStatus.EXPLORATION:
                raise ValueError("MAYBE requires exploration plan status.")
        elif self.recommendation_reference is FitRecommendation.GO:
            if self.plan_status is not ActionPlanStatus.FULL:
                raise ValueError("GO requires full plan status.")
            if not any(
                action.action_type in {ActionType.PREPARATION, ActionType.SUBMISSION}
                for action in self.actions
            ):
                raise ValueError("GO requires preparation or submission tasks.")
        return self


def _normalize_text(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split())


def _resolve_pointer(document: dict, reference: ActionInputReference) -> object:
    pointer = _ACTION_INPUT_POINTERS[reference]
    current: object = document
    for raw_segment in pointer[1:].split("/"):
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            raise ValueError(f"Action input reference does not exist: {pointer}")
    if current is None or current == [] or current == {}:
        raise ValueError(f"Action input reference has no usable value: {pointer}")
    return current


def _planner_inputs(
    *,
    eligibility: EligibilityAssessmentV3,
    fit: FitEvaluation,
    profile: UserProfile,
    preferences: FitPreferences,
    evidence_bundle: CompetitionEvidenceBundle,
    model_uncertainties: list[str],
    unresolved_conflicts: list[str],
) -> dict:
    return {
        "eligibility": eligibility.model_dump(mode="json"),
        "fit": fit.model_dump(mode="json"),
        "profile": profile.model_dump(mode="json"),
        "preferences": preferences.model_dump(mode="json"),
        "model_uncertainties": model_uncertainties,
        "unresolved_conflicts": unresolved_conflicts,
        "source_failures": [
            {
                "source_id": source.source_id,
                "url": str(source.final_url or source.source_url),
                "status": source.extraction_status.value,
            }
            for source in evidence_bundle.sources
            if source.extraction_status is not EvidenceExtractionStatus.SUCCESS
        ],
    }


def validate_action_plan_draft(
    draft: ActionPlanDraft,
    *,
    recommendation: FitRecommendation,
    evidence_bundle: CompetitionEvidenceBundle,
    inputs: dict,
) -> ActionPlanDraft:
    """Reject invented requirements, deadlines, references, and unsafe ordering."""

    all_sources = {source.source_id: source for source in evidence_bundle.sources}
    successful_sources = {
        source_id: source
        for source_id, source in all_sources.items()
        if source.extraction_status is EvidenceExtractionStatus.SUCCESS
    }
    ids = [action.action_id for action in draft.actions]
    if len(ids) != len(set(ids)):
        raise ValueError("Action IDs must be unique.")
    if len(draft.suggested_sequence) != len(set(draft.suggested_sequence)):
        raise ValueError("Suggested sequence cannot contain duplicates.")
    if set(draft.suggested_sequence) != set(ids):
        raise ValueError("Suggested sequence must contain every action exactly once.")
    positions = {
        action_id: index for index, action_id in enumerate(draft.suggested_sequence)
    }

    verification_ids = {
        action.action_id
        for action in draft.actions
        if action.action_type is ActionType.VERIFICATION
    }
    for action in draft.actions:
        for reference in action.competition_evidence:
            source = successful_sources.get(reference.source_id)
            if source is None:
                raise ValueError(
                    "Action evidence source does not exist or was not usable: "
                    f"{reference.source_id}"
                )
            if _normalize_text(reference.excerpt) not in _normalize_text(
                source.extracted_text or ""
            ):
                raise ValueError(
                    "Action evidence excerpt is not present in its source "
                    f"{reference.source_id}: "
                    f"{_normalize_text(reference.excerpt)[:180]!r}"
                )
        for reference in action.input_refs:
            try:
                validated_reference = ActionInputReference(reference)
            except ValueError as exc:
                raise ValueError(
                    f"Unknown Action Planner input reference: {reference}"
                ) from exc
            _resolve_pointer(inputs, validated_reference)
        for dependency in action.dependency_ids:
            if dependency not in positions:
                raise ValueError(f"Unknown action dependency: {dependency}")
            if positions[dependency] >= positions[action.action_id]:
                raise ValueError("Dependencies must precede dependent actions.")

        if (
            recommendation is FitRecommendation.VERIFY_FIRST
            and action.action_type
            in {ActionType.SUBMISSION, ActionType.MANDATORY_EVENT}
            and not verification_ids.intersection(action.dependency_ids)
        ):
            raise ValueError(
                "VERIFY_FIRST submission/event tasks must depend on verification."
            )

    if recommendation is FitRecommendation.VERIFY_FIRST:
        first_action = next(
            action
            for action in draft.actions
            if action.action_id == draft.suggested_sequence[0]
        )
        if first_action.action_type is not ActionType.VERIFICATION:
            raise ValueError("VERIFY_FIRST must begin with verification.")
    return draft


def _resolved_submission_deadline(
    intelligence: CompetitionIntelligence,
    evidence_bundle: CompetitionEvidenceBundle,
) -> ActionDeadline | None:
    """Attach only a resolved typed deadline backed by literal fetched evidence."""

    sources = {
        source.source_id: source
        for source in evidence_bundle.sources
        if source.extraction_status is EvidenceExtractionStatus.SUCCESS
    }
    claims = {claim.claim_id: claim for claim in intelligence.claims}
    for resolved in intelligence.resolved_fields:
        if (
            resolved.field_path != "/deadline"
            or resolved.resolution_status is not ResolutionStatus.RESOLVED
            or resolved.conflicting_claim_ids
            or not isinstance(resolved.effective_value, dict)
        ):
            continue
        try:
            value = DeadlineValue.model_validate_json(
                json.dumps(resolved.effective_value)
            )
        except ValueError:
            continue
        if value.deadline_type is not DeadlineType.SUBMISSION:
            continue

        references: list[CompetitionEvidenceReference] = []
        for claim_id in resolved.supporting_claim_ids:
            claim = claims.get(claim_id)
            if claim is None or claim.field_path != "/deadline":
                continue
            source = sources.get(claim.evidence_locator or "")
            if source is None or _normalize_text(claim.evidence_text) not in (
                _normalize_text(source.extracted_text or "")
            ):
                continue
            references.append(
                CompetitionEvidenceReference(
                    source_id=source.source_id,
                    excerpt=claim.evidence_text,
                )
            )
        if references:
            return ActionDeadline(value=value, competition_evidence=references)
    return None


def _aggregate_usage(usages: list[object | None]) -> object | None:
    usable = [usage for usage in usages if usage is not None]
    if not usable:
        return None
    if len(usable) == 1:
        return usable[0]
    names = (
        "prompt_token_count",
        "candidates_token_count",
        "total_token_count",
        "cached_content_token_count",
        "thoughts_token_count",
    )
    totals = {
        name: sum(getattr(usage, name, 0) or 0 for usage in usable) for name in names
    }
    return SimpleNamespace(**totals, call_count=len(usable))


def _plan_prompt(
    *,
    record: CompetitionRecord,
    intelligence: CompetitionIntelligence,
    evidence_bundle: CompetitionEvidenceBundle,
    eligibility: EligibilityAssessmentV3,
    fit: FitEvaluation,
    profile: UserProfile,
    preferences: FitPreferences,
    model_uncertainties: list[str],
    unresolved_conflicts: list[str],
) -> str:
    return f"""
You produce a concise, UI-ready PrizeHunter ActionPlanDraft as strict JSON.

This is planning only. You MUST NOT claim to execute, register, submit, email,
create repositories, create calendar events, or write to any external system.
Every action remains a suggestion for human review.

Responsibility boundaries:
- Organizer requirements come only from exact EVIDENCE excerpts. A task with
  basis `confirmed_requirement` MUST cite a short contiguous exact excerpt.
- `ai_suggestion` is planning judgement, not an organizer fact. Phrase it as a
  suggestion and trace it to an approved input ref when no organizer evidence exists.
- `verification` means the fact is not confirmed. State the uncertainty, explain
  why it matters, and name where the human should check. Never write it as settled.
- Never use this prompt itself as organizer evidence.

Recommendation gate for this run: `{fit.recommendation.value}`.
- verify_first: begin with verification; do not pretend full execution can start.
  Any submission or mandatory-event task must depend on a verification action.
- maybe: produce a minimal exploration/decision plan focused on largest unknowns.
- go: produce a complete but small execution checklist.

Use 3-12 practical actions. Follow the compact response keys in schema order:
objective, actions, sequence, unresolved. Within each action use id, title,
reason, kind, basis, priority, effort, timing, evidence, refs, depends_on,
human_confirmation, uncertainty, confirm_at. Every id must match
`action_[a-z0-9_]+` and appear once in sequence. Dependencies must appear earlier.
Every item needs a rough effort range. Reuse FIT_EVALUATION effort rather than
inventing a contradictory total. Use timing for labels such as Today or Next 2
days. Do not generate a deadline field: the application attaches only a resolved,
source-backed organizer submission deadline after validation. Use an empty string
for uncertainty and confirm_at when they do not apply.

Every refs entry must be one of: eligibility_status, eligibility_blockers,
eligibility_uncertainties, model_uncertainties, source_conflicts, source_failures,
fit_recommendation, fit_effort, fit_risks, fit_uncertainties,
profile_available_time, preferences_available_hours, preferences_goals,
preferences_reusable_assets. Never invent a key. Evidence quote values must be
literal source substrings; do not paraphrase, join sentences, or insert ellipses.

ELIGIBILITY_ASSESSMENT:
{eligibility.model_dump_json(indent=2)}

FIT_EVALUATION:
{fit.model_dump_json(indent=2)}

USER_PROFILE:
{profile.model_dump_json(indent=2)}

FIT_PREFERENCES:
{preferences.model_dump_json(indent=2)}

MODEL_UNCERTAINTIES:
{model_uncertainties}

UNRESOLVED_CONFLICTS:
{unresolved_conflicts}

COMPETITION_RECORD:
{record.model_dump_json(indent=2)}

COMPETITION_INTELLIGENCE:
{intelligence.model_dump_json(indent=2)}

EVIDENCE:
{format_evidence_for_model(evidence_bundle)}
""".strip()


def _skipped_plan(
    *,
    competition_id: str,
    fit: FitEvaluation,
    generated_at: datetime,
) -> ActionPlan:
    reasons = [item.text for item in fit.why]
    recommendation = fit.recommendation
    label = (
        "not eligible" if recommendation is FitRecommendation.NOT_ELIGIBLE else "skip"
    )
    return ActionPlan(
        plan_status=ActionPlanStatus.SKIPPED,
        competition_id=competition_id,
        profile_id=fit.profile_id,
        profile_version=fit.profile_version,
        fit_evaluation_version=fit.evaluation_version,
        recommendation_reference=recommendation,
        generated_at=generated_at,
        overall_objective=f"Stop planning because the recommendation is {label}.",
        stopped_reasons=reasons or [f"Recommendation is {label}."],
        inference_skipped=True,
        skip_reason=(
            "Confirmed hard ineligibility; Action Planner inference was unnecessary."
            if recommendation is FitRecommendation.NOT_ELIGIBLE
            else "SKIP is not overridden; Action Planner inference was unnecessary."
        ),
    )


def _effort_summary(
    actions: list[ActionItem],
    *,
    fit: FitEvaluation,
) -> PlanEffortSummary:
    plan_minimum = sum(action.estimated_effort.minimum_hours for action in actions)
    plan_maximum = sum(action.estimated_effort.maximum_hours for action in actions)
    fit_effort = fit.effort_estimate
    fit_minimum = fit_effort.minimum_hours if fit_effort is not None else None
    fit_maximum = fit_effort.maximum_hours if fit_effort is not None else None

    if fit.recommendation in {
        FitRecommendation.VERIFY_FIRST,
        FitRecommendation.MAYBE,
    }:
        relationship = EffortRelationship.LIMITED_SCOPE
        note = (
            "This limited verification/exploration plan does not replace the full Fit "
            "effort estimate."
        )
    elif fit_minimum is None or fit_maximum is None:
        relationship = EffortRelationship.UNKNOWN
        note = "Fit did not provide a comparable hour range."
    else:
        overlaps = plan_minimum <= fit_maximum and plan_maximum >= fit_minimum
        if overlaps:
            relationship = EffortRelationship.ALIGNED_WITH_FIT
            note = "Task decomposition broadly overlaps the Fit effort range."
        else:
            relationship = EffortRelationship.UPDATED_FROM_DECOMPOSITION
            note = (
                "Plan effort updated based on task decomposition; review the difference "
                "from the directional Fit estimate."
            )
    return PlanEffortSummary(
        plan_minimum_hours=plan_minimum,
        plan_maximum_hours=plan_maximum,
        fit_minimum_hours=fit_minimum,
        fit_maximum_hours=fit_maximum,
        relationship=relationship,
        note=note,
    )


def plan_actions(
    *,
    competition_id: str,
    record: CompetitionRecord,
    intelligence: CompetitionIntelligence,
    evidence_bundle: CompetitionEvidenceBundle,
    eligibility: EligibilityAssessmentV3,
    fit: FitEvaluation,
    profile: UserProfile,
    preferences: FitPreferences,
    model_uncertainties: list[str],
    unresolved_conflicts: list[str],
    generated_at: datetime,
    generator: Callable[
        [str, type], tuple[object, object | None]
    ],
    model: str,
) -> tuple[ActionPlan, object | None]:
    """Generate a guarded checklist or deterministically skip planning."""

    if fit.competition_id != competition_id:
        raise ValueError("Fit and Action Plan competition references must match.")
    if fit.profile_id != profile.profile_id or fit.profile_version != profile.version:
        raise ValueError("Fit and Action Plan profile references must match.")
    if fit.eligibility_status is not eligibility.overall_status:
        raise ValueError("Fit and Action Plan eligibility references must match.")
    if fit.recommendation in {
        FitRecommendation.NOT_ELIGIBLE,
        FitRecommendation.SKIP,
    }:
        return _skipped_plan(
            competition_id=competition_id,
            fit=fit,
            generated_at=generated_at,
        ), None

    inputs = _planner_inputs(
        eligibility=eligibility,
        fit=fit,
        profile=profile,
        preferences=preferences,
        evidence_bundle=evidence_bundle,
        model_uncertainties=model_uncertainties,
        unresolved_conflicts=unresolved_conflicts,
    )
    prompt = _plan_prompt(
        record=record,
        intelligence=intelligence,
        evidence_bundle=evidence_bundle,
        eligibility=eligibility,
        fit=fit,
        profile=profile,
        preferences=preferences,
        model_uncertainties=model_uncertainties,
        unresolved_conflicts=unresolved_conflicts,
    )
    usages: list[object | None] = []
    for attempt in range(2):
        parsed, usage = generator(prompt, ActionPlanDraft)
        usages.append(usage)
        draft = (
            parsed
            if isinstance(parsed, ActionPlanDraft)
            else ActionPlanDraft.model_validate(parsed)
        )
        try:
            validate_action_plan_draft(
                draft,
                recommendation=fit.recommendation,
                evidence_bundle=evidence_bundle,
                inputs=inputs,
            )
            break
        except ValueError as exc:
            if attempt == 1:
                raise
            prompt += (
                "\n\nVALIDATION FEEDBACK FROM THE APPLICATION:\n"
                f"{exc}\n"
                "Regenerate the entire JSON once. Preserve the recommendation gate. "
                "Correct only with literal source excerpts or approved input refs; "
                "do not turn suggestions or unknowns into organizer facts."
            )

    verification_ids = {
        action.action_id
        for action in draft.actions
        if action.action_type is ActionType.VERIFICATION
    }
    organizer_deadline = _resolved_submission_deadline(
        intelligence,
        evidence_bundle,
    )
    actions = [
        ActionItem(
            action_id=action.action_id,
            title=action.title,
            short_reason=action.short_reason,
            action_type=action.action_type,
            basis=action.basis,
            priority=action.priority,
            estimated_effort=action.estimated_effort,
            deadline=(
                organizer_deadline
                if action.action_type is ActionType.SUBMISSION
                else None
            ),
            suggested_timing=action.suggested_timing,
            competition_evidence=[
                reference.to_reference() for reference in action.competition_evidence
            ],
            input_refs=[
                ActionInputReference(reference) for reference in action.input_refs
            ],
            dependency_ids=action.dependency_ids,
            requires_human_confirmation=action.requires_human_confirmation,
            uncertainty=action.uncertainty or None,
            confirmation_target=action.confirmation_target or None,
            confirmation_target_source_id=(
                action.competition_evidence[0].source_id
                if action.action_type is ActionType.VERIFICATION
                and action.competition_evidence
                else None
            ),
            status=(
                ActionStatus.BLOCKED_PENDING_VERIFICATION
                if verification_ids.intersection(action.dependency_ids)
                else ActionStatus.NOT_STARTED
            ),
        )
        for action in draft.actions
    ]
    plan_status = {
        FitRecommendation.GO: ActionPlanStatus.FULL,
        FitRecommendation.MAYBE: ActionPlanStatus.EXPLORATION,
        FitRecommendation.VERIFY_FIRST: ActionPlanStatus.VERIFICATION_FIRST,
    }[fit.recommendation]
    return (
        ActionPlan(
            plan_status=plan_status,
            competition_id=competition_id,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            fit_evaluation_version=fit.evaluation_version,
            recommendation_reference=fit.recommendation,
            generated_at=generated_at,
            overall_objective=draft.overall_objective,
            actions=actions,
            suggested_sequence=draft.suggested_sequence,
            estimated_total_effort=_effort_summary(actions, fit=fit),
            unresolved_items=draft.unresolved_items,
            model=model,
        ),
        _aggregate_usage(usages),
    )
