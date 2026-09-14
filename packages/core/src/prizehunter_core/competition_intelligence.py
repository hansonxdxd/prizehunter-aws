"""Versioned claim provenance and conservative field-resolution contracts."""

from __future__ import annotations

import json
import math
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)


class SourceType(StrEnum):
    """Document role; this enum is not an authority ranking."""

    OFFICIAL_AMENDMENT = "official_amendment"
    OFFICIAL_RULES = "official_rules"
    OFFICIAL_COMPETITION_PAGE = "official_competition_page"
    OFFICIAL_FAQ = "official_faq"
    OFFICIAL_REGISTRATION = "official_registration"
    OFFICIAL_ORGANIZER_POST = "official_organizer_post"
    COMPETITION_PLATFORM = "competition_platform"
    AGGREGATOR = "aggregator"
    THIRD_PARTY_REPOST = "third_party_repost"


class AuthorityClass(StrEnum):
    """Source-control relationship used as evidence, never as overwrite priority."""

    OFFICIAL_PRIMARY = "official_primary"
    OFFICIAL_DELEGATED = "official_delegated"
    ORGANIZER_CONTROLLED_PLATFORM = "organizer_controlled_platform"
    THIRD_PARTY = "third_party"
    UNKNOWN = "unknown"


class ScopeKind(StrEnum):
    """The competition slice to which a claim applies."""

    WHOLE_COMPETITION = "whole_competition"
    TRACK = "track"
    PRIZE_TIER = "prize_tier"
    STAGE = "stage"
    ENTRANT_CATEGORY = "entrant_category"


class ClaimScope(BaseModel):
    """Explicit scope prevents one track or stage claim leaking into another."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: ScopeKind = ScopeKind.WHOLE_COMPETITION
    identifier: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_identifier(self) -> Self:
        if self.kind is ScopeKind.WHOLE_COMPETITION and self.identifier is not None:
            raise ValueError("Whole-competition scope cannot have an identifier.")
        if self.kind is not ScopeKind.WHOLE_COMPETITION and self.identifier is None:
            raise ValueError("Specific scope kinds require an identifier.")
        return self


def _validate_json_value(value: JsonValue) -> JsonValue:
    """Reject values that Python permits but JSON cannot safely round-trip."""

    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Claim values cannot contain NaN or infinity.")
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Claim object keys must be strings.")
            _validate_json_value(item)
    return value


def _validate_field_path(value: str) -> str:
    """Validate a small JSON Pointer convention without implementing traversal."""

    if not value.startswith("/") or value == "/" or value.endswith("/"):
        raise ValueError("field_path must be a non-root absolute JSON Pointer.")
    segments = value[1:].split("/")
    if any(not segment for segment in segments):
        raise ValueError("field_path cannot contain empty path segments.")
    for segment in segments:
        index = 0
        while index < len(segment):
            if segment[index] == "~":
                if index + 1 >= len(segment) or segment[index + 1] not in {"0", "1"}:
                    raise ValueError("field_path uses only JSON Pointer ~0/~1 escapes.")
                index += 2
                continue
            index += 1
    return value


class FieldClaim(BaseModel):
    """One source-backed assertion; it is not a final competition fact."""

    model_config = ConfigDict(extra="forbid", strict=True)

    claim_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    field_path: str
    value: JsonValue
    normalized_value: JsonValue = None
    source_url: AnyHttpUrl
    source_type: SourceType
    source_title: str | None = Field(default=None, min_length=1)
    authority_class: AuthorityClass
    observed_at: datetime
    source_published_at: datetime | None = None
    source_updated_at: datetime | None = None
    evidence_text: str = Field(min_length=1)
    evidence_locator: str | None = Field(default=None, min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    scope: ClaimScope = Field(default_factory=ClaimScope)
    supersedes_claim_ids: list[str] = Field(default_factory=list)
    uncertainty: str | None = Field(default=None, min_length=1)

    @field_validator("field_path")
    @classmethod
    def validate_field_path(cls, value: str) -> str:
        return _validate_field_path(value)

    @field_validator("value", "normalized_value")
    @classmethod
    def validate_value(cls, value: JsonValue) -> JsonValue:
        return _validate_json_value(value)

    @model_validator(mode="after")
    def validate_supersession(self) -> Self:
        if self.claim_id in self.supersedes_claim_ids:
            raise ValueError("A claim cannot supersede itself.")
        if len(self.supersedes_claim_ids) != len(set(self.supersedes_claim_ids)):
            raise ValueError("supersedes_claim_ids cannot contain duplicates.")
        return self


class ResolutionStatus(StrEnum):
    """Minimal states for an effective field value."""

    RESOLVED = "resolved"
    UNRESOLVED_CONFLICT = "unresolved_conflict"
    PROVISIONAL = "provisional"


class ResolverType(StrEnum):
    """Who or what produced the resolution record."""

    DETERMINISTIC = "deterministic"
    HUMAN = "human"
    MODEL = "model"
    UNRESOLVED = "unresolved"


class ResolvedField(BaseModel):
    """Resolution state for one field path and one explicit scope."""

    model_config = ConfigDict(extra="forbid", strict=True)

    field_path: str
    scope: ClaimScope = Field(default_factory=ClaimScope)
    resolution_status: ResolutionStatus
    effective_value: JsonValue = None
    supporting_claim_ids: list[str] = Field(default_factory=list)
    conflicting_claim_ids: list[str] = Field(default_factory=list)
    superseded_claim_ids: list[str] = Field(default_factory=list)
    resolution_reason: str = Field(min_length=1)
    resolved_at: datetime | None = None
    resolver_type: ResolverType
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    uncertainty: str | None = Field(default=None, min_length=1)

    @field_validator("field_path")
    @classmethod
    def validate_field_path(cls, value: str) -> str:
        return _validate_field_path(value)

    @field_validator("effective_value")
    @classmethod
    def validate_effective_value(cls, value: JsonValue) -> JsonValue:
        return _validate_json_value(value)

    @model_validator(mode="after")
    def validate_resolution_state(self) -> Self:
        reference_groups = (
            self.supporting_claim_ids,
            self.conflicting_claim_ids,
            self.superseded_claim_ids,
        )
        for references in reference_groups:
            if len(references) != len(set(references)):
                raise ValueError("Claim reference lists cannot contain duplicates.")
        all_references = [
            reference for group in reference_groups for reference in group
        ]
        if len(all_references) != len(set(all_references)):
            raise ValueError("A claim cannot have multiple resolution roles.")

        if self.resolution_status is ResolutionStatus.UNRESOLVED_CONFLICT:
            if self.effective_value is not None:
                raise ValueError("Unresolved conflicts cannot have an effective value.")
            if self.resolver_type is not ResolverType.UNRESOLVED:
                raise ValueError(
                    "Unresolved conflicts require resolver_type=unresolved."
                )
            if len(self.conflicting_claim_ids) < 2:
                raise ValueError("Unresolved conflicts require at least two claims.")
            if self.resolved_at is not None:
                raise ValueError("Unresolved conflicts cannot have resolved_at.")
            if self.uncertainty is None:
                raise ValueError("Unresolved conflicts must explain their uncertainty.")
        elif self.resolver_type is ResolverType.UNRESOLVED:
            raise ValueError(
                "Only unresolved conflicts may use resolver_type=unresolved."
            )
        elif not self.supporting_claim_ids:
            raise ValueError(
                "Resolved or provisional fields require supporting claims."
            )

        if self.resolution_status is ResolutionStatus.RESOLVED:
            if self.resolved_at is None:
                raise ValueError("Resolved fields require resolved_at.")
        elif self.resolved_at is not None:
            raise ValueError("Only resolved fields may have resolved_at.")
        return self


class CompetitionIntelligence(BaseModel):
    """Additive sidecar that leaves the current CompetitionRecord unchanged."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = Field(default="1.0", pattern=r"^1\.0$")
    competition_id: str = Field(min_length=1)
    competition_record_version: int | None = Field(default=None, ge=1)
    claims: list[FieldClaim] = Field(default_factory=list)
    resolved_fields: list[ResolvedField] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_claim_graph(self) -> Self:
        claims_by_id = {claim.claim_id: claim for claim in self.claims}
        if len(claims_by_id) != len(self.claims):
            raise ValueError("claim_id must be unique within a sidecar.")

        for claim in self.claims:
            for target_id in claim.supersedes_claim_ids:
                target = claims_by_id.get(target_id)
                if target is None:
                    raise ValueError(
                        f"Unknown superseded claim reference: {target_id}."
                    )
                if (target.field_path, target.scope) != (claim.field_path, claim.scope):
                    raise ValueError(
                        "Supersession references must share field path and scope."
                    )

        self._validate_no_supersession_cycles(claims_by_id)

        resolution_keys: set[tuple[str, str, str | None]] = set()
        for field in self.resolved_fields:
            key = (field.field_path, field.scope.kind.value, field.scope.identifier)
            if key in resolution_keys:
                raise ValueError(
                    "Each field path and scope may have one resolution record."
                )
            resolution_keys.add(key)
            references = (
                field.supporting_claim_ids
                + field.conflicting_claim_ids
                + field.superseded_claim_ids
            )
            for claim_id in references:
                claim = claims_by_id.get(claim_id)
                if claim is None:
                    raise ValueError(f"Unknown resolution claim reference: {claim_id}.")
                if (claim.field_path, claim.scope) != (field.field_path, field.scope):
                    raise ValueError(
                        "Resolution references must share field path and scope."
                    )
        return self

    @staticmethod
    def _validate_no_supersession_cycles(claims_by_id: dict[str, FieldClaim]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(claim_id: str) -> None:
            if claim_id in visiting:
                raise ValueError("Claim supersession graph cannot contain a cycle.")
            if claim_id in visited:
                return
            visiting.add(claim_id)
            for target_id in claims_by_id[claim_id].supersedes_claim_ids:
                visit(target_id)
            visiting.remove(claim_id)
            visited.add(claim_id)

        for claim_id in claims_by_id:
            visit(claim_id)


def _comparison_value(claim: FieldClaim) -> JsonValue:
    return claim.normalized_value if claim.normalized_value is not None else claim.value


def _value_key(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def resolve_field_claims(
    claims: list[FieldClaim], *, resolved_at: datetime
) -> ResolvedField:
    """Resolve only agreement or explicit official-amendment supersession.

    Authority classes and timestamps never resolve a conflict by themselves.
    """

    if not claims:
        raise ValueError("At least one claim is required.")
    claims_by_id = {claim.claim_id: claim for claim in claims}
    if len(claims_by_id) != len(claims):
        raise ValueError("claim_id must be unique within a resolution attempt.")
    field_path = claims[0].field_path
    scope = claims[0].scope
    if any((claim.field_path, claim.scope) != (field_path, scope) for claim in claims):
        raise ValueError(
            "All claims in one resolution attempt need one path and scope."
        )
    for claim in claims:
        if any(
            target_id not in claims_by_id for target_id in claim.supersedes_claim_ids
        ):
            raise ValueError(
                "Supersession references must exist in the resolution attempt."
            )

    groups: dict[str, list[FieldClaim]] = {}
    for claim in claims:
        groups.setdefault(_value_key(_comparison_value(claim)), []).append(claim)

    if len(groups) == 1:
        return ResolvedField(
            field_path=field_path,
            scope=scope,
            resolution_status=ResolutionStatus.PROVISIONAL,
            effective_value=_comparison_value(claims[0]),
            supporting_claim_ids=[claim.claim_id for claim in claims],
            resolution_reason=(
                "Available claims agree, but no explicit amendment establishes a final "
                "controlling value."
            ),
            resolver_type=ResolverType.DETERMINISTIC,
            confidence=min(claim.confidence for claim in claims),
            uncertainty="The controlling source may still be updated or incomplete.",
        )

    superseding_candidates: list[FieldClaim] = []
    for candidate in claims:
        if candidate.source_type is not SourceType.OFFICIAL_AMENDMENT:
            continue
        candidate_key = _value_key(_comparison_value(candidate))
        conflicting_ids = {
            claim.claim_id
            for key, grouped_claims in groups.items()
            if key != candidate_key
            for claim in grouped_claims
        }
        if conflicting_ids and conflicting_ids <= set(candidate.supersedes_claim_ids):
            timestamps_are_valid = True
            for target_id in conflicting_ids:
                target_published_at = claims_by_id[target_id].source_published_at
                if (
                    candidate.source_published_at is not None
                    and target_published_at is not None
                    and candidate.source_published_at <= target_published_at
                ):
                    timestamps_are_valid = False
                    break
            if timestamps_are_valid:
                superseding_candidates.append(candidate)

    if len(superseding_candidates) == 1:
        winner = superseding_candidates[0]
        winner_key = _value_key(_comparison_value(winner))
        supporting = [
            claim.claim_id
            for claim in claims
            if _value_key(_comparison_value(claim)) == winner_key
        ]
        superseded = [
            claim.claim_id
            for claim in claims
            if _value_key(_comparison_value(claim)) != winner_key
        ]
        return ResolvedField(
            field_path=field_path,
            scope=scope,
            resolution_status=ResolutionStatus.RESOLVED,
            effective_value=_comparison_value(winner),
            supporting_claim_ids=supporting,
            superseded_claim_ids=superseded,
            resolution_reason=(
                "An official amendment explicitly supersedes every conflicting "
                "earlier claim."
            ),
            resolved_at=resolved_at,
            resolver_type=ResolverType.DETERMINISTIC,
            confidence=winner.confidence,
        )

    return ResolvedField(
        field_path=field_path,
        scope=scope,
        resolution_status=ResolutionStatus.UNRESOLVED_CONFLICT,
        conflicting_claim_ids=[claim.claim_id for claim in claims],
        resolution_reason=(
            "Claims disagree and no single official amendment explicitly supersedes "
            "every conflicting claim."
        ),
        resolver_type=ResolverType.UNRESOLVED,
        uncertainty="The controlling competition fact requires source or human review.",
    )
