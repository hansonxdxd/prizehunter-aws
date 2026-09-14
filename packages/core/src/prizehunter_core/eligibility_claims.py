"""Source-backed typed eligibility claims produced from an Evidence Bundle."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from prizehunter_core.competition_intelligence import (
    AuthorityClass,
    ClaimScope,
    CompetitionIntelligence,
    FieldClaim,
    ResolutionStatus,
    ResolvedField,
    ResolverType,
    ScopeKind,
    SourceType,
    resolve_field_claims,
)
from prizehunter_core.deadlines import DeadlineValue
from prizehunter_core.evidence import (
    AuthorityHint,
    CompetitionEvidenceBundle,
    CompetitionEvidenceSource,
    EvidenceExtractionStatus,
    EvidenceSourceType,
)
from prizehunter_core.expanded_eligibility import (
    AgeRequirement,
    CitizenshipRequirement,
    EducationRequirement,
    EligibilityDivision,
    EntityRequirement,
    EntrantStatusRequirement,
    ExistingWorkRequirement,
    ResidenceRequirement,
    TeamSizeRequirement,
)

_SIMPLE_MODELS: dict[str, type[BaseModel]] = {
    "/deadline": DeadlineValue,
    "/eligibility/residence": ResidenceRequirement,
    "/eligibility/age": AgeRequirement,
    "/eligibility/team_size": TeamSizeRequirement,
    "/eligibility/citizenship": CitizenshipRequirement,
    "/eligibility/education_status": EducationRequirement,
    "/eligibility/entrant_status": EntrantStatusRequirement,
    "/eligibility/entity": EntityRequirement,
    "/eligibility/existing_work": ExistingWorkRequirement,
}
_DEADLINE_TIMEZONE_OFFSETS = {
    "PST": "-08:00",
    "PDT": "-07:00",
    "EST": "-05:00",
    "EDT": "-04:00",
}


class EligibilityClaimDraft(BaseModel):
    """Untrusted structured model output; validated before becoming a FieldClaim."""

    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(min_length=2)
    value_json: str = Field(min_length=2)
    source_id: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    uncertainty: str | None = None
    scope_kind: Literal["whole_competition", "entrant_category"] = "whole_competition"
    scope_identifier: str | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> EligibilityClaimDraft:
        if (self.scope_kind == "whole_competition") != (self.scope_identifier is None):
            raise ValueError("Only entrant-category scope may have an identifier.")
        return self


class EligibilityClaimBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[EligibilityClaimDraft] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class RejectedClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    field_path: str
    source_id: str
    reason: str


class ClaimBuildResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    intelligence: CompetitionIntelligence
    rejected_claims: list[RejectedClaimDraft] = Field(default_factory=list)
    model_uncertainties: list[str] = Field(default_factory=list)


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _source_type(source: CompetitionEvidenceSource) -> SourceType:
    mapping = {
        EvidenceSourceType.RULES: SourceType.OFFICIAL_RULES,
        EvidenceSourceType.FAQ: SourceType.OFFICIAL_FAQ,
        EvidenceSourceType.REGISTRATION: SourceType.OFFICIAL_REGISTRATION,
        EvidenceSourceType.ANNOUNCEMENT: SourceType.OFFICIAL_ORGANIZER_POST,
        EvidenceSourceType.PLATFORM: SourceType.COMPETITION_PLATFORM,
        EvidenceSourceType.AGGREGATOR: SourceType.AGGREGATOR,
    }
    return mapping.get(source.source_type, SourceType.OFFICIAL_COMPETITION_PAGE)


def _authority(source: CompetitionEvidenceSource) -> AuthorityClass:
    mapping = {
        AuthorityHint.ORGANIZER_CONTROLLED: AuthorityClass.OFFICIAL_PRIMARY,
        AuthorityHint.PLATFORM: AuthorityClass.ORGANIZER_CONTROLLED_PLATFORM,
        AuthorityHint.THIRD_PARTY: AuthorityClass.THIRD_PARTY,
        AuthorityHint.UNKNOWN: AuthorityClass.UNKNOWN,
    }
    return mapping[source.authority_hint]


def _value_model(path: str) -> type[BaseModel] | None:
    if path.startswith("/eligibility/divisions/"):
        return EligibilityDivision
    return _SIMPLE_MODELS.get(path)


def _claim_id(draft: EligibilityClaimDraft) -> str:
    digest = hashlib.sha256(
        f"{draft.source_id}|{draft.field_path}|{draft.scope_identifier}|{draft.value_json}".encode()
    ).hexdigest()[:16]
    return f"url.{digest}"


def validate_claim_drafts(
    batch: EligibilityClaimBatch,
    bundle: CompetitionEvidenceBundle,
    *,
    competition_id: str,
    observed_at: datetime,
    mapping_description: str = "Model mapped agreeing typed values to exact source excerpts; "
    "the mapping remains auditable through the supporting claims.",
) -> ClaimBuildResult:
    sources = {source.source_id: source for source in bundle.sources}
    claims: list[FieldClaim] = []
    rejected: list[RejectedClaimDraft] = []
    for draft in batch.claims:
        source = sources.get(draft.source_id)
        model = _value_model(draft.field_path)
        reason: str | None = None
        value: dict | None = None
        if (
            source is None
            or source.extraction_status is not EvidenceExtractionStatus.SUCCESS
        ):
            reason = "source_id is absent or does not refer to successful evidence"
        elif model is None:
            reason = "field_path is outside the approved typed eligibility contract"
        elif _normalize_text(draft.evidence_text) not in _normalize_text(
            source.extracted_text or ""
        ):
            reason = "evidence_text is not a verbatim substring of the cited source"
        else:
            try:
                typed_value = model.model_validate_json(draft.value_json)
                if isinstance(typed_value, DeadlineValue):
                    normalized_timezone = _DEADLINE_TIMEZONE_OFFSETS.get(
                        typed_value.timezone or ""
                    )
                    if normalized_timezone is not None:
                        typed_value = typed_value.model_copy(
                            update={"timezone": normalized_timezone}
                        )
                value = typed_value.model_dump(mode="json")
            except ValueError as exc:
                reason = f"value_json does not match the typed contract: {exc}"
        if reason:
            rejected.append(
                RejectedClaimDraft(
                    field_path=draft.field_path,
                    source_id=draft.source_id,
                    reason=reason,
                )
            )
            continue
        assert source is not None and value is not None
        scope = ClaimScope(
            kind=(
                ScopeKind.ENTRANT_CATEGORY
                if draft.scope_kind == "entrant_category"
                else ScopeKind.WHOLE_COMPETITION
            ),
            identifier=draft.scope_identifier,
        )
        claims.append(
            FieldClaim(
                claim_id=_claim_id(draft),
                field_path=draft.field_path,
                value=value,
                normalized_value=value,
                source_url=source.final_url or source.source_url,
                source_type=_source_type(source),
                source_title=source.title,
                authority_class=_authority(source),
                observed_at=observed_at,
                evidence_text=draft.evidence_text,
                evidence_locator=draft.source_id,
                confidence=draft.confidence,
                scope=scope,
                uncertainty=draft.uncertainty,
            )
        )

    grouped: dict[tuple[str, ScopeKind, str | None], list[FieldClaim]] = defaultdict(
        list
    )
    for claim in claims:
        grouped[(claim.field_path, claim.scope.kind, claim.scope.identifier)].append(
            claim
        )
    resolutions: list[ResolvedField] = []
    for grouped_claims in grouped.values():
        baseline = resolve_field_claims(grouped_claims, resolved_at=observed_at)
        if baseline.resolution_status is ResolutionStatus.UNRESOLVED_CONFLICT:
            resolutions.append(baseline)
            continue
        confidently_grounded = all(
            claim.confidence >= 0.9 and claim.uncertainty is None
            for claim in grouped_claims
        )
        if confidently_grounded:
            resolutions.append(
                baseline.model_copy(
                    update={
                        "resolution_status": ResolutionStatus.RESOLVED,
                        "resolved_at": observed_at,
                        "resolver_type": ResolverType.MODEL,
                        "resolution_reason": mapping_description,
                        "uncertainty": None,
                    }
                )
            )
        else:
            resolutions.append(baseline)
    return ClaimBuildResult(
        intelligence=CompetitionIntelligence(
            competition_id=competition_id,
            claims=claims,
            resolved_fields=resolutions,
        ),
        rejected_claims=rejected,
        model_uncertainties=batch.uncertainties,
    )
