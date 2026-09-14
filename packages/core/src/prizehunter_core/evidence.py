"""Executable provenance for the documents fetched by the URL ingestion layer."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


class EvidenceContentType(StrEnum):
    HTML = "html"
    PDF = "pdf"
    UNKNOWN = "unknown"


class EvidenceSourceType(StrEnum):
    OFFICIAL_PAGE = "official_page"
    RULES = "rules"
    FAQ = "faq"
    GUIDELINES = "guidelines"
    REGISTRATION = "registration"
    ANNOUNCEMENT = "announcement"
    PLATFORM = "platform"
    AGGREGATOR = "aggregator"
    UNKNOWN = "unknown"


class EvidenceRelation(StrEnum):
    SEED = "seed"
    SAME_ORIGIN = "same_origin"
    RELATED_EXTERNAL = "related_external"


class AuthorityHint(StrEnum):
    ORGANIZER_CONTROLLED = "organizer_controlled"
    PLATFORM = "platform"
    THIRD_PARTY = "third_party"
    UNKNOWN = "unknown"


class EvidenceExtractionStatus(StrEnum):
    SUCCESS = "success"
    INACCESSIBLE = "inaccessible"
    LOGIN_REQUIRED = "login_required"
    DYNAMIC_PAGE = "dynamic_page"
    BROKEN_LINK = "broken_link"
    TIMEOUT = "timeout"
    UNSUPPORTED_CONTENT = "unsupported_content"
    PARSER_FAILED = "parser_failed"
    ROBOTS_DISALLOWED = "robots_disallowed"
    TOO_LARGE = "too_large"
    DUPLICATE = "duplicate"


class EvidenceRetrievalTrace(BaseModel):
    """One bounded retrieval/tool call, kept separate from competition facts."""

    model_config = ConfigDict(extra="forbid", strict=True)

    method: str = Field(min_length=1)
    status: str = Field(min_length=1)
    requested_url: AnyHttpUrl | None = None
    elapsed_seconds: float = Field(ge=0)
    model: str | None = None
    prompt_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    thinking_tokens: int | None = Field(default=None, ge=0)
    tool_use_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class EvidenceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    http_status: int | None = Field(default=None, ge=100, le=599)
    parser: str | None = None
    depth: int = Field(ge=0)
    page_count: int | None = Field(default=None, ge=1)
    links_discovered: int = Field(default=0, ge=0)
    duplicate_of: str | None = None
    retrieval_method: str = Field(default="http", min_length=1)
    retrieval_status: str | None = None
    citation_url: str | None = None
    classification_confidence: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class CompetitionEvidenceSource(BaseModel):
    """One retrieval attempt and its extracted document text, if successful."""

    model_config = ConfigDict(extra="forbid", strict=True)

    source_id: str = Field(min_length=1, pattern=r"^src_[a-f0-9]{12}$")
    source_url: AnyHttpUrl
    final_url: AnyHttpUrl | None = None
    source_type: EvidenceSourceType
    content_type: EvidenceContentType
    authority_hint: AuthorityHint
    relation_to_seed: EvidenceRelation
    title: str | None = None
    retrieved_at: datetime
    extraction_status: EvidenceExtractionStatus
    extracted_text: str | None = None
    content_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    discovered_from: str | None = None
    metadata: EvidenceMetadata

    @model_validator(mode="after")
    def validate_success_payload(self) -> CompetitionEvidenceSource:
        if self.extraction_status is EvidenceExtractionStatus.SUCCESS:
            if not self.extracted_text or not self.content_sha256:
                raise ValueError(
                    "Successful evidence requires text and a content hash."
                )
        elif self.extracted_text is not None:
            raise ValueError(
                "Failed or duplicate evidence cannot carry extracted text."
            )
        return self


class CompetitionEvidenceBundle(BaseModel):
    """What Phase 3 fetched; it is deliberately separate from factual claims."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0"] = "1.0"
    seed_url: AnyHttpUrl
    started_at: datetime
    completed_at: datetime
    sources: list[CompetitionEvidenceSource]
    retrieval_traces: list[EvidenceRetrievalTrace] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bundle(self) -> CompetitionEvidenceBundle:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at.")
        ids = [source.source_id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source_id must be unique within an evidence bundle.")
        if (
            not self.sources
            or self.sources[0].relation_to_seed is not EvidenceRelation.SEED
        ):
            raise ValueError("The first evidence source must represent the seed URL.")
        return self
