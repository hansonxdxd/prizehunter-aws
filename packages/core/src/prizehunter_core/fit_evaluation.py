"""Traceable same-model Fit judgement, kept separate from hard eligibility."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from types import SimpleNamespace
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from prizehunter_core.competition_intelligence import CompetitionIntelligence
from prizehunter_core.eligibility import EligibilityStatus
from prizehunter_core.eligibility_assessment_v3 import EligibilityAssessmentV3
from prizehunter_core.evidence import CompetitionEvidenceBundle, EvidenceExtractionStatus
from prizehunter_core.evidence_formatting import format_evidence_for_model
from prizehunter_core.schemas import CompetitionRecord
from prizehunter_core.user_profile import UserProfile


class ParticipationMode(StrEnum):
    ONLINE = "online"
    IN_PERSON = "in_person"
    HYBRID = "hybrid"


class RewardType(StrEnum):
    CASH = "cash"
    NON_CASH = "non_cash"
    CREDITS = "credits"
    SUBSCRIPTION = "subscription"
    HARDWARE = "hardware"
    GRANT = "grant"
    INCUBATION = "incubation"
    TRAVEL_SUPPORT = "travel_support"
    OTHER = "other"


class FitRecommendation(StrEnum):
    GO = "go"
    MAYBE = "maybe"
    VERIFY_FIRST = "verify_first"
    SKIP = "skip"
    NOT_ELIGIBLE = "not_eligible"


class FitDimensionName(StrEnum):
    SKILL_CAPABILITY = "skill_capability"
    BUILD_FEASIBILITY = "build_feasibility"
    TIME_EFFORT = "time_effort"
    REWARD_ATTRACTIVENESS = "reward_attractiveness"
    PARTICIPATION_BURDEN = "participation_burden"
    STRATEGIC_INTEREST = "strategic_interest"


class FitRating(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class EffortLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class FitInputReference(StrEnum):
    """Short approved keys mapped deterministically to input JSON pointers."""

    PROFILE_COUNTRY = "profile_country"
    PROFILE_AGE = "profile_age"
    PROFILE_PARTICIPATION = "profile_participation"
    PROFILE_SKILLS = "profile_skills"
    PROFILE_TECHNICAL_CAPABILITY = "profile_technical_capability"
    PROFILE_AVAILABLE_TIME = "profile_available_time"
    PROFILE_WILLINGNESS_TO_LEARN = "profile_willingness_to_learn"
    PROFILE_CANDIDATE_PROJECT = "profile_candidate_project"
    PREFERENCES_PARTICIPATION = "preferences_participation"
    PREFERENCES_TRAVEL = "preferences_travel"
    PREFERENCES_FRESH_BUILD = "preferences_fresh_build"
    PREFERENCES_AVAILABLE_HOURS = "preferences_available_hours"
    PREFERENCES_REWARDS = "preferences_rewards"
    PREFERENCES_INTERESTS = "preferences_interests"
    PREFERENCES_GOALS = "preferences_goals"
    PREFERENCES_REUSABLE_ASSETS = "preferences_reusable_assets"
    ELIGIBILITY_STATUS = "eligibility_status"
    ELIGIBILITY_BLOCKERS = "eligibility_blockers"
    ELIGIBILITY_UNCERTAINTIES = "eligibility_uncertainties"
    ELIGIBILITY_DEADLINE = "eligibility_deadline"


_INPUT_REFERENCE_POINTERS = {
    FitInputReference.PROFILE_COUNTRY: "/profile/country",
    FitInputReference.PROFILE_AGE: "/profile/age",
    FitInputReference.PROFILE_PARTICIPATION: "/profile/team_preference",
    FitInputReference.PROFILE_SKILLS: "/profile/skills",
    FitInputReference.PROFILE_TECHNICAL_CAPABILITY: "/profile/technical_capability",
    FitInputReference.PROFILE_AVAILABLE_TIME: "/profile/available_time",
    FitInputReference.PROFILE_WILLINGNESS_TO_LEARN: "/profile/willingness_to_learn_new_tech",
    FitInputReference.PROFILE_CANDIDATE_PROJECT: "/profile/candidate_project",
    FitInputReference.PREFERENCES_PARTICIPATION: "/preferences/preferred_participation_modes",
    FitInputReference.PREFERENCES_TRAVEL: "/preferences/willingness_to_travel",
    FitInputReference.PREFERENCES_FRESH_BUILD: "/preferences/willingness_to_build_fresh",
    FitInputReference.PREFERENCES_AVAILABLE_HOURS: "/preferences/available_hours_before_deadline",
    FitInputReference.PREFERENCES_REWARDS: "/preferences/preferred_reward_types",
    FitInputReference.PREFERENCES_INTERESTS: "/preferences/interests",
    FitInputReference.PREFERENCES_GOALS: "/preferences/strategic_goals",
    FitInputReference.PREFERENCES_REUSABLE_ASSETS: "/preferences/reusable_assets",
    FitInputReference.ELIGIBILITY_STATUS: "/eligibility/overall_status",
    FitInputReference.ELIGIBILITY_BLOCKERS: "/eligibility/confirmed_blockers",
    FitInputReference.ELIGIBILITY_UNCERTAINTIES: "/eligibility/uncertainties",
    FitInputReference.ELIGIBILITY_DEADLINE: "/eligibility/base_assessment/deadline_state",
}


def _unique_strings(value: list[str]) -> list[str]:
    if any(not item.strip() for item in value):
        raise ValueError("String lists cannot contain blank values.")
    if len({item.casefold().strip() for item in value}) != len(value):
        raise ValueError("String lists cannot contain duplicates.")
    return value


class FitPreferences(BaseModel):
    """Small competition-specific preference record supplied by the user."""

    model_config = ConfigDict(extra="forbid", strict=True)

    preferences_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    preferred_participation_modes: list[ParticipationMode] = Field(default_factory=list)
    willingness_to_travel: bool | None = None
    maximum_travel_days: int | None = Field(default=None, ge=0)
    willingness_to_build_fresh: bool | None = None
    available_hours_before_deadline: float | None = Field(default=None, ge=0)
    preferred_reward_types: list[RewardType] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    strategic_goals: list[str] = Field(default_factory=list)
    reusable_assets: list[str] = Field(default_factory=list)
    preference_uncertainties: list[str] = Field(default_factory=list)

    _validate_text_lists = field_validator(
        "interests",
        "strategic_goals",
        "reusable_assets",
        "preference_uncertainties",
    )(_unique_strings)

    @field_validator("preferred_participation_modes", "preferred_reward_types")
    @classmethod
    def validate_unique_enums(cls, value: list) -> list:
        if len(value) != len(set(value)):
            raise ValueError("Preference enum lists cannot contain duplicates.")
        return value

    @model_validator(mode="after")
    def validate_travel_days(self) -> Self:
        if self.willingness_to_travel is False and self.maximum_travel_days not in {
            None,
            0,
        }:
            raise ValueError("Unwillingness to travel conflicts with travel days.")
        return self

    def has_decision_context(self) -> bool:
        return any(
            (
                self.preferred_participation_modes,
                self.willingness_to_travel is not None,
                self.willingness_to_build_fresh is not None,
                self.available_hours_before_deadline is not None,
                self.preferred_reward_types,
                self.interests,
                self.strategic_goals,
                self.reusable_assets,
            )
        )


class CompetitionEvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class FitRationale(BaseModel):
    """Short decision rationale with source or validated input references."""

    model_config = ConfigDict(extra="forbid", strict=True)

    text: str = Field(min_length=1)
    competition_evidence: list[CompetitionEvidenceReference] = Field(
        default_factory=list
    )
    input_refs: list[FitInputReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_reference(self) -> Self:
        if not self.competition_evidence and not self.input_refs:
            raise ValueError("Every rationale needs evidence or an input reference.")
        return self


class FitDimension(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dimension: FitDimensionName
    rating: FitRating
    score: int = Field(ge=0, le=100)
    explanation: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    competition_evidence: list[CompetitionEvidenceReference] = Field(
        default_factory=list
    )
    input_refs: list[FitInputReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_reference(self) -> Self:
        if not self.competition_evidence and not self.input_refs:
            raise ValueError("Every Fit dimension needs a traceable reference.")
        return self


class FitDimensionDraft(BaseModel):
    """One model-produced dimension; the object key fixes its identity."""

    model_config = ConfigDict(extra="forbid", strict=True)

    rating: FitRating
    score: int = Field(ge=0, le=100)
    explanation: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    competition_evidence: list[CompetitionEvidenceReference] = Field(
        default_factory=list
    )
    input_refs: list[FitInputReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_reference(self) -> Self:
        if not self.competition_evidence and not self.input_refs:
            raise ValueError("Every Fit dimension needs a traceable reference.")
        return self


class FitDimensionsDraft(BaseModel):
    """Fixed six-key model contract prevents duplicate or omitted dimensions."""

    model_config = ConfigDict(extra="forbid", strict=True)

    skill_capability: FitDimensionDraft
    build_feasibility: FitDimensionDraft
    time_effort: FitDimensionDraft
    reward_attractiveness: FitDimensionDraft
    participation_burden: FitDimensionDraft
    strategic_interest: FitDimensionDraft

    def to_dimensions(self) -> list[FitDimension]:
        return [
            FitDimension(
                dimension=FitDimensionName(name),
                **value.model_dump(),
            )
            for name, value in self
        ]


class EffortEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    level: EffortLevel
    minimum_hours: float | None = Field(default=None, ge=0)
    maximum_hours: float | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0, le=1)
    drivers: list[str] = Field(min_length=1)
    competition_evidence: list[CompetitionEvidenceReference] = Field(
        default_factory=list
    )
    input_refs: list[FitInputReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_estimate(self) -> Self:
        if (self.minimum_hours is None) != (self.maximum_hours is None):
            raise ValueError("Hour estimates require both range bounds or neither.")
        if (
            self.minimum_hours is not None
            and self.maximum_hours is not None
            and self.minimum_hours > self.maximum_hours
        ):
            raise ValueError("minimum_hours cannot exceed maximum_hours.")
        if not self.competition_evidence and not self.input_refs:
            raise ValueError("Effort estimates need traceable inputs.")
        return self


class RewardComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reward_type: RewardType
    label: str = Field(min_length=1)
    organizer_stated_value: str | None = None
    competition_evidence: list[CompetitionEvidenceReference] = Field(min_length=1)


class FitEvaluationDraft(BaseModel):
    """Untrusted model judgement before deterministic policy guards."""

    model_config = ConfigDict(extra="forbid")

    recommendation: Literal["go", "maybe", "verify_first", "skip"]
    overall_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    dimensions: FitDimensionsDraft
    effort_estimate: EffortEstimate
    reward_components: list[RewardComponent] = Field(default_factory=list)
    why: list[FitRationale] = Field(min_length=1)
    risks: list[FitRationale] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class FitEvaluation(BaseModel):
    """Versioned AI judgement record, separate from facts and user profile."""

    model_config = ConfigDict(extra="forbid", strict=True)

    evaluation_version: Literal["1.0"] = "1.0"
    competition_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_version: int = Field(ge=1)
    preferences_id: str = Field(min_length=1)
    preferences_version: int = Field(ge=1)
    eligibility_status: EligibilityStatus
    recommendation: FitRecommendation
    overall_score: int | None = Field(default=None, ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    dimensions: list[FitDimension] = Field(default_factory=list)
    effort_estimate: EffortEstimate | None = None
    reward_components: list[RewardComponent] = Field(default_factory=list)
    why: list[FitRationale] = Field(min_length=1)
    risks: list[FitRationale] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    model: str | None = None
    generated_at: datetime
    inference_skipped: bool = False
    skip_reason: str | None = None

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.eligibility_status is EligibilityStatus.INELIGIBLE:
            if self.recommendation is not FitRecommendation.NOT_ELIGIBLE:
                raise ValueError("Ineligible opportunities must be NOT_ELIGIBLE.")
            if not self.inference_skipped or self.model is not None:
                raise ValueError("Ineligible Fit must skip inference.")
            if (
                self.overall_score is not None
                or self.dimensions
                or self.effort_estimate
            ):
                raise ValueError("Skipped Fit cannot contain model judgement scores.")
        else:
            if self.inference_skipped or not self.model:
                raise ValueError("Evaluated Fit must record the configured model.")
            if self.overall_score is None or self.effort_estimate is None:
                raise ValueError("Evaluated Fit requires score and effort estimate.")
            if len(self.dimensions) != len(FitDimensionName):
                raise ValueError("Evaluated Fit requires all six dimensions.")
        if (
            self.eligibility_status is EligibilityStatus.UNCERTAIN
            and self.recommendation is FitRecommendation.GO
        ):
            raise ValueError("Uncertain eligibility cannot receive unconditional GO.")
        return self


def _normalize_text(value: str) -> str:
    # PDF and HTML parsers can represent the same visible text with different
    # Unicode compatibility forms and line-wrap whitespace. Ignore whitespace
    # only; the exact character sequence and punctuation must still be present.
    return "".join(unicodedata.normalize("NFKC", value).split())


def _resolve_pointer(document: dict, reference: str | FitInputReference) -> object:
    try:
        reference = FitInputReference(reference)
    except ValueError as exc:
        raise ValueError(f"Unsupported Fit input reference: {reference}") from exc
    pointer = _INPUT_REFERENCE_POINTERS[reference]
    current: object = document
    for raw_segment in pointer[1:].split("/"):
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif (
            isinstance(current, list)
            and segment.isdigit()
            and int(segment) < len(current)
        ):
            current = current[int(segment)]
        else:
            raise ValueError(f"Input reference does not exist: {pointer}")
    if current is None:
        raise ValueError(f"Input reference points to an unknown value: {pointer}")
    return current


def _iter_reference_holders(draft: FitEvaluationDraft):
    yield from (value for _, value in draft.dimensions)
    yield draft.effort_estimate
    yield from draft.reward_components
    yield from draft.why
    yield from draft.risks


def validate_fit_draft(
    draft: FitEvaluationDraft,
    *,
    evidence_bundle: CompetitionEvidenceBundle,
    profile: UserProfile,
    preferences: FitPreferences,
    eligibility: EligibilityAssessmentV3,
) -> FitEvaluationDraft:
    """Reject invented evidence and references before accepting model judgement."""

    sources = {
        source.source_id: source
        for source in evidence_bundle.sources
        if source.extraction_status is EvidenceExtractionStatus.SUCCESS
    }
    inputs = {
        "profile": profile.model_dump(mode="json"),
        "preferences": preferences.model_dump(mode="json"),
        "eligibility": eligibility.model_dump(mode="json"),
    }
    for holder in _iter_reference_holders(draft):
        for reference in holder.competition_evidence:
            source = sources.get(reference.source_id)
            if source is None:
                raise ValueError(
                    f"Fit evidence source does not exist or was not usable: {reference.source_id}"
                )
            if _normalize_text(reference.excerpt) not in _normalize_text(
                source.extracted_text or ""
            ):
                preview = _normalize_text(reference.excerpt)[:180]
                raise ValueError(
                    "Fit evidence excerpt is not present in its source "
                    f"{reference.source_id}: {preview!r}"
                )
        for reference in getattr(holder, "input_refs", []):
            _resolve_pointer(inputs, reference)
    return draft


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


def _fit_prompt(
    *,
    record: CompetitionRecord,
    intelligence: CompetitionIntelligence,
    evidence_bundle: CompetitionEvidenceBundle,
    eligibility: EligibilityAssessmentV3,
    profile: UserProfile,
    preferences: FitPreferences,
) -> str:
    return f"""
You produce a concise PrizeHunter opportunity Fit judgement as strict JSON.

Responsibility boundaries:
- Organizer facts come only from COMPETITION_RECORD, COMPETITION_INTELLIGENCE,
  and exact EVIDENCE excerpts. Never invent a requirement, deadline, prize, or event.
- User facts come only from USER_PROFILE and FIT_PREFERENCES. Never invent a skill,
  asset, budget, availability, or preference.
- Your output is AI judgement. It cannot change ELIGIBILITY_ASSESSMENT or override a blocker.
- Do not reveal hidden chain-of-thought. Give short decision rationale only.

Evaluate Required Effort vs Available Capacity vs Expected Value. `dimensions`
is a fixed object with exactly these six keys: skill_capability,
build_feasibility, time_effort, reward_attractiveness, participation_burden,
strategic_interest. Fill every key once; do not emit a dimension list.
The 0-100 score is only a rough ranking aid, not scientific precision.
Hours are explicitly an estimate. List concrete effort drivers.
Fresh-work requirements increase effort but NEVER cause SKIP by themselves.
Distinguish cash from credits, subscriptions, hardware, grants, incubation,
travel support, and other non-cash rewards. Organizer-stated value is not personal value.
Low or missing inputs must lower confidence and appear in uncertainties.

Every competition_evidence reference must use a SOURCE id and a short exact excerpt.
Every input_refs entry must be selected exactly from the schema's approved short
enum keys, for example `profile_technical_capability`, `preferences_goals`, or
`eligibility_status`. Never invent, combine, or append text to these keys.
Evidence excerpts must be one contiguous verbatim substring: never insert `...`
or combine distant passages. Every dimension, effort estimate, why item, and risk
needs at least one traceable evidence or input reference. Reward components require
competition evidence. Do not copy organizer facts without a cited excerpt.

ELIGIBILITY_ASSESSMENT:
{eligibility.model_dump_json(indent=2)}

USER_PROFILE:
{profile.model_dump_json(indent=2)}

FIT_PREFERENCES:
{preferences.model_dump_json(indent=2)}

COMPETITION_RECORD:
{record.model_dump_json(indent=2)}

COMPETITION_INTELLIGENCE:
{intelligence.model_dump_json(indent=2)}

EVIDENCE:
{format_evidence_for_model(evidence_bundle)}
""".strip()


def _ineligible_result(
    *,
    competition_id: str,
    eligibility: EligibilityAssessmentV3,
    profile: UserProfile,
    preferences: FitPreferences,
    generated_at: datetime,
) -> FitEvaluation:
    blockers = eligibility.confirmed_blockers
    first_reason = blockers[0].reason if blockers else "Hard eligibility is ineligible."
    return FitEvaluation(
        competition_id=competition_id,
        profile_id=profile.profile_id,
        profile_version=profile.version,
        preferences_id=preferences.preferences_id,
        preferences_version=preferences.version,
        eligibility_status=EligibilityStatus.INELIGIBLE,
        recommendation=FitRecommendation.NOT_ELIGIBLE,
        confidence=1.0,
        why=[
            FitRationale(
                text=first_reason,
                input_refs=[FitInputReference.ELIGIBILITY_BLOCKERS],
            )
        ],
        uncertainties=[],
        generated_at=generated_at,
        inference_skipped=True,
        skip_reason="Confirmed hard-eligibility blocker; full Fit inference was unnecessary.",
    )


def evaluate_fit(
    *,
    competition_id: str,
    record: CompetitionRecord,
    intelligence: CompetitionIntelligence,
    evidence_bundle: CompetitionEvidenceBundle,
    eligibility: EligibilityAssessmentV3,
    profile: UserProfile,
    preferences: FitPreferences,
    generated_at: datetime,
    generator: Callable[
        [str, type], tuple[object, object | None]
    ],
    model: str,
) -> tuple[FitEvaluation, object | None]:
    """Run guarded Fit judgement; ineligible opportunities make zero model calls."""

    if eligibility.overall_status is EligibilityStatus.INELIGIBLE:
        return (
            _ineligible_result(
                competition_id=competition_id,
                eligibility=eligibility,
                profile=profile,
                preferences=preferences,
                generated_at=generated_at,
            ),
            None,
        )

    prompt = _fit_prompt(
        record=record,
        intelligence=intelligence,
        evidence_bundle=evidence_bundle,
        eligibility=eligibility,
        profile=profile,
        preferences=preferences,
    )
    usages: list[object | None] = []
    for attempt in range(2):
        parsed, usage = generator(prompt, FitEvaluationDraft)
        usages.append(usage)
        draft = (
            parsed
            if isinstance(parsed, FitEvaluationDraft)
            else FitEvaluationDraft.model_validate(parsed)
        )
        try:
            validate_fit_draft(
                draft,
                evidence_bundle=evidence_bundle,
                profile=profile,
                preferences=preferences,
                eligibility=eligibility,
            )
            break
        except ValueError as exc:
            if attempt == 1:
                raise
            prompt += (
                "\n\nVALIDATION FEEDBACK FROM THE APPLICATION:\n"
                f"{exc}\n"
                "Regenerate the entire JSON once. Correct the rejected reference. "
                "Evidence excerpts must be literal contiguous source text, except that "
                "source line-wrap whitespace may be omitted. Do not paraphrase or join "
                "separate sentences."
            )
    recommendation = FitRecommendation(draft.recommendation)
    if eligibility.overall_status is EligibilityStatus.UNCERTAIN:
        if recommendation is FitRecommendation.GO:
            recommendation = FitRecommendation.VERIFY_FIRST
    elif recommendation is FitRecommendation.VERIFY_FIRST:
        recommendation = FitRecommendation.MAYBE

    confidence = draft.confidence
    uncertainties = list(draft.uncertainties)
    if not preferences.has_decision_context():
        confidence = min(confidence, 0.5)
        uncertainties.append(
            "Fit preferences contain no decision context; recommendation confidence is capped."
        )
        if recommendation is FitRecommendation.GO:
            recommendation = FitRecommendation.MAYBE

    return (
        FitEvaluation(
            competition_id=competition_id,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            preferences_id=preferences.preferences_id,
            preferences_version=preferences.version,
            eligibility_status=eligibility.overall_status,
            recommendation=recommendation,
            overall_score=draft.overall_score,
            confidence=confidence,
            dimensions=draft.dimensions.to_dimensions(),
            effort_estimate=draft.effort_estimate,
            reward_components=draft.reward_components,
            why=draft.why,
            risks=draft.risks,
            uncertainties=list(dict.fromkeys(uncertainties)),
            model=model,
            generated_at=generated_at,
        ),
        _aggregate_usage(usages),
    )
