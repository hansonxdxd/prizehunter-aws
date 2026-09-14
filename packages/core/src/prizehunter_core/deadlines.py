"""Typed deadline adapters and conservative passed-deadline assessment."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta, timezone
from datetime import date as Date
from datetime import time as Time
from enum import StrEnum
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from prizehunter_core.competition_intelligence import (
    ClaimScope,
    CompetitionIntelligence,
    ResolutionStatus,
)
from prizehunter_core.schemas import CompetitionRecord


class DeadlineType(StrEnum):
    """Small controlled set that can grow without assuming one deadline per event."""

    REGISTRATION = "registration"
    PROPOSAL = "proposal"
    SUBMISSION = "submission"
    PRELIMINARY_SUBMISSION = "preliminary_submission"
    SEMIFINAL_SUBMISSION = "semifinal_submission"
    FINAL_SUBMISSION = "final_submission"
    FINAL_DEMO = "final_demo"
    OTHER = "other"


_DEFAULT_DEADLINE_TYPE = DeadlineType("submission")


class TimezoneStatus(StrEnum):
    """Whether and how the source establishes deadline timezone semantics."""

    EXPLICIT = "explicit"
    LOCAL_UNSPECIFIED = "local_unspecified"
    UNKNOWN = "unknown"


class DeadlineValue(BaseModel):
    """Minimum typed deadline without inventing time or timezone information."""

    model_config = ConfigDict(extra="forbid", strict=True)

    date: Date
    time: Time | None = None
    timezone: str | None = Field(default=None, min_length=1)
    timezone_status: TimezoneStatus = TimezoneStatus.UNKNOWN
    deadline_type: DeadlineType = DeadlineType.SUBMISSION

    @model_validator(mode="after")
    def validate_time_and_timezone(self) -> Self:
        if self.time is not None and self.time.tzinfo is not None:
            raise ValueError(
                "Deadline time must be naive; timezone is stored separately."
            )
        if self.time is None:
            if self.timezone is not None:
                raise ValueError("A date-only deadline cannot carry a timezone value.")
            if self.timezone_status is not TimezoneStatus.UNKNOWN:
                raise ValueError(
                    "A date-only deadline must have unknown timezone status."
                )
        elif self.timezone_status is TimezoneStatus.EXPLICIT:
            if self.timezone is None:
                raise ValueError("Explicit timezone status requires a timezone value.")
        elif self.timezone is not None:
            raise ValueError(
                "Only explicit timezone status may carry a timezone value."
            )
        return self


class DeadlineAdapterStatus(StrEnum):
    """Consumer-visible state of one requested deadline path and scope."""

    RESOLVED = "resolved"
    PROVISIONAL = "provisional"
    UNRESOLVED_CONFLICT = "unresolved_conflict"
    MISSING = "missing"
    LEGACY_UNPARSED = "legacy_unparsed"
    SIDECAR_UNPARSED = "sidecar_unparsed"


class DeadlineInputSource(StrEnum):
    """Which compatibility boundary produced the consumer state."""

    SIDECAR = "sidecar"
    LEGACY = "legacy"
    NONE = "none"


class DeadlineState(BaseModel):
    """Typed adapter output consumed without inspecting raw claims or legacy text."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: DeadlineAdapterStatus
    deadline: DeadlineValue | None = None
    field_path: str = Field(pattern=r"^/.+")
    scope: ClaimScope = Field(default_factory=ClaimScope)
    source: DeadlineInputSource
    claim_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        has_deadline = self.status in {
            DeadlineAdapterStatus.RESOLVED,
            DeadlineAdapterStatus.PROVISIONAL,
        }
        if has_deadline and self.deadline is None:
            raise ValueError("Resolved or provisional deadline states require a value.")
        if not has_deadline and self.deadline is not None:
            raise ValueError(
                "Unknown or unparsed deadline states cannot carry a value."
            )
        if len(self.claim_ids) != len(set(self.claim_ids)):
            raise ValueError("claim_ids cannot contain duplicates.")
        required_sources = {
            DeadlineAdapterStatus.RESOLVED: DeadlineInputSource.SIDECAR,
            DeadlineAdapterStatus.UNRESOLVED_CONFLICT: DeadlineInputSource.SIDECAR,
            DeadlineAdapterStatus.LEGACY_UNPARSED: DeadlineInputSource.LEGACY,
            DeadlineAdapterStatus.SIDECAR_UNPARSED: DeadlineInputSource.SIDECAR,
        }
        required_source = required_sources.get(self.status)
        if required_source is not None and self.source is not required_source:
            raise ValueError(
                f"{self.status.value} requires source={required_source.value}."
            )
        return self


class DeadlinePassStatus(StrEnum):
    """Safe deterministic comparison outcome for one typed deadline state."""

    PASSED = "passed"
    NOT_PASSED = "not_passed"
    UNCERTAIN = "uncertain"


class DeadlinePassResult(BaseModel):
    """Consumer result; uncertain is preferred over an unsafe time assumption."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: DeadlinePassStatus
    reason: str = Field(min_length=1)


_ISO_DEADLINE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:[T ](?P<time>\d{2}:\d{2}(?::\d{2})?)"
    r"(?:\s*(?P<timezone>Z|[+-]\d{2}:\d{2}|local(?:\s+time)?|"
    r"[A-Za-z_+-]+/[A-Za-z0-9_+./-]+))?)?$",
    re.IGNORECASE,
)
_LEGACY_LONG_DATE = re.compile(
    r"^(?P<date>[A-Za-z]+\s+\d{1,2},\s+\d{4})\s+at\s+"
    r"(?P<time>\d{1,2}:\d{2}\s+[AP]M)\s+"
    r"(?P<timezone>Pacific Time|Eastern Time|PST|PDT|EST|EDT|UTC)$",
    re.IGNORECASE,
)
_LEGACY_TIMEZONES = {
    "pacific time": "America/Los_Angeles",
    "eastern time": "America/New_York",
    "pst": "-08:00",
    "pdt": "-07:00",
    "est": "-05:00",
    "edt": "-04:00",
    "utc": "UTC",
}


def _parse_deadline_value(
    value: object, *, deadline_type: DeadlineType
) -> DeadlineValue | None:
    if isinstance(value, dict):
        try:
            return DeadlineValue.model_validate_json(json.dumps(value))
        except (TypeError, ValidationError):
            return None
    if not isinstance(value, str):
        return None

    iso_match = _ISO_DEADLINE.fullmatch(value.strip())
    if iso_match:
        parsed_date = Date.fromisoformat(iso_match.group("date"))
        time_text = iso_match.group("time")
        if time_text is None:
            return DeadlineValue(date=parsed_date, deadline_type=deadline_type)
        parsed_time = Time.fromisoformat(time_text)
        timezone_text = iso_match.group("timezone")
        if timezone_text is None:
            timezone_status = TimezoneStatus.UNKNOWN
            normalized_timezone = None
        elif timezone_text.casefold().startswith("local"):
            timezone_status = TimezoneStatus.LOCAL_UNSPECIFIED
            normalized_timezone = None
        else:
            timezone_status = TimezoneStatus.EXPLICIT
            normalized_timezone = "UTC" if timezone_text == "Z" else timezone_text
        return DeadlineValue(
            date=parsed_date,
            time=parsed_time,
            timezone=normalized_timezone,
            timezone_status=timezone_status,
            deadline_type=deadline_type,
        )

    long_match = _LEGACY_LONG_DATE.fullmatch(value.strip())
    if long_match:
        parsed_date = datetime.strptime(long_match.group("date"), "%B %d, %Y").date()
        parsed_time = datetime.strptime(long_match.group("time"), "%I:%M %p").time()
        normalized_timezone = _LEGACY_TIMEZONES[long_match.group("timezone").casefold()]
        return DeadlineValue(
            date=parsed_date,
            time=parsed_time,
            timezone=normalized_timezone,
            timezone_status=TimezoneStatus.EXPLICIT,
            deadline_type=deadline_type,
        )
    return None


def adapt_deadline(
    *,
    competition_record: CompetitionRecord | None = None,
    intelligence: CompetitionIntelligence | None = None,
    field_path: str = "/deadline",
    scope: ClaimScope | None = None,
    deadline_type: DeadlineType = _DEFAULT_DEADLINE_TYPE,
) -> DeadlineState:
    """Adapt one exact deadline path/scope, preferring explicit sidecar state.

    A sidecar conflict or unparseable effective value never falls back to legacy
    `CompetitionRecord.deadline` text.
    """

    requested_scope = scope or ClaimScope()
    matching_resolutions = (
        [
            field
            for field in intelligence.resolved_fields
            if field.field_path == field_path and field.scope == requested_scope
        ]
        if intelligence is not None
        else []
    )

    if matching_resolutions:
        resolution = matching_resolutions[0]
        all_claim_ids = list(
            dict.fromkeys(
                resolution.supporting_claim_ids
                + resolution.conflicting_claim_ids
                + resolution.superseded_claim_ids
            )
        )
        if resolution.resolution_status is ResolutionStatus.UNRESOLVED_CONFLICT:
            return DeadlineState(
                status=DeadlineAdapterStatus.UNRESOLVED_CONFLICT,
                field_path=field_path,
                scope=requested_scope,
                source=DeadlineInputSource.SIDECAR,
                claim_ids=all_claim_ids,
                reason=resolution.resolution_reason,
            )
        deadline = _parse_deadline_value(
            resolution.effective_value,
            deadline_type=deadline_type,
        )
        if deadline is None:
            return DeadlineState(
                status=DeadlineAdapterStatus.SIDECAR_UNPARSED,
                field_path=field_path,
                scope=requested_scope,
                source=DeadlineInputSource.SIDECAR,
                claim_ids=all_claim_ids,
                reason="The sidecar effective value is not a supported DeadlineValue.",
            )
        status = (
            DeadlineAdapterStatus.RESOLVED
            if resolution.resolution_status is ResolutionStatus.RESOLVED
            else DeadlineAdapterStatus.PROVISIONAL
        )
        return DeadlineState(
            status=status,
            deadline=deadline,
            field_path=field_path,
            scope=requested_scope,
            source=DeadlineInputSource.SIDECAR,
            claim_ids=all_claim_ids,
            reason=resolution.resolution_reason,
        )

    matching_claim_ids = (
        [
            claim.claim_id
            for claim in intelligence.claims
            if claim.field_path == field_path and claim.scope == requested_scope
        ]
        if intelligence is not None
        else []
    )
    if matching_claim_ids:
        return DeadlineState(
            status=DeadlineAdapterStatus.MISSING,
            field_path=field_path,
            scope=requested_scope,
            source=DeadlineInputSource.SIDECAR,
            claim_ids=matching_claim_ids,
            reason="Sidecar claims exist, but no resolution record is available.",
        )

    if competition_record is None or competition_record.deadline is None:
        return DeadlineState(
            status=DeadlineAdapterStatus.MISSING,
            field_path=field_path,
            scope=requested_scope,
            source=DeadlineInputSource.NONE,
            reason="No sidecar resolution or legacy deadline is available.",
        )

    legacy_deadline = _parse_deadline_value(
        competition_record.deadline,
        deadline_type=deadline_type,
    )
    if legacy_deadline is None:
        return DeadlineState(
            status=DeadlineAdapterStatus.LEGACY_UNPARSED,
            field_path=field_path,
            scope=requested_scope,
            source=DeadlineInputSource.LEGACY,
            reason="Legacy deadline text is outside the deterministic parser subset.",
        )
    return DeadlineState(
        status=DeadlineAdapterStatus.PROVISIONAL,
        deadline=legacy_deadline,
        field_path=field_path,
        scope=requested_scope,
        source=DeadlineInputSource.LEGACY,
        reason="Legacy deadline parsed deterministically but has no sidecar resolution.",
    )


def _timezone_info(value: str) -> timezone | ZoneInfo | None:
    if value == "UTC":
        return UTC
    offset_match = re.fullmatch(r"([+-])(\d{2}):(\d{2})", value)
    if offset_match:
        hours = int(offset_match.group(2))
        minutes = int(offset_match.group(3))
        if hours > 23 or minutes > 59:
            return None
        delta = timedelta(hours=hours, minutes=minutes)
        if offset_match.group(1) == "-":
            delta = -delta
        try:
            return timezone(delta)
        except ValueError:
            return None
    try:
        return ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        return None


def _safe_deadline_datetime(value: DeadlineValue) -> datetime | None:
    if (
        value.time is None
        or value.timezone_status is not TimezoneStatus.EXPLICIT
        or value.timezone is None
    ):
        return None
    timezone_info = _timezone_info(value.timezone)
    if timezone_info is None:
        return None
    naive = datetime.combine(value.date, value.time)
    if isinstance(timezone_info, timezone):
        return naive.replace(tzinfo=timezone_info)

    valid_candidates: list[datetime] = []
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=timezone_info, fold=fold)
        round_trip = candidate.astimezone(UTC).astimezone(timezone_info)
        if round_trip.replace(tzinfo=None) == naive:
            valid_candidates.append(candidate)
    if not valid_candidates:
        return None
    if len({candidate.utcoffset() for candidate in valid_candidates}) > 1:
        return None
    return valid_candidates[0]


def assess_deadline_passed(
    deadline_state: DeadlineState, *, now: datetime
) -> DeadlinePassResult:
    """Compare only a resolved deadline with complete, unambiguous timezone data."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware.")
    if deadline_state.status is not DeadlineAdapterStatus.RESOLVED:
        return DeadlinePassResult(
            status=DeadlinePassStatus.UNCERTAIN,
            reason="Only a resolved sidecar deadline can drive a hard time gate.",
        )
    if deadline_state.deadline is None:
        return DeadlinePassResult(
            status=DeadlinePassStatus.UNCERTAIN,
            reason="No typed deadline value is available.",
        )
    deadline_at = _safe_deadline_datetime(deadline_state.deadline)
    if deadline_at is None:
        if deadline_state.deadline.date > now.date():
            return DeadlinePassResult(
                status=DeadlinePassStatus.NOT_PASSED,
                reason=(
                    "The resolved deadline calendar date is later than the current "
                    "calendar date, so it is safely treated as not passed without "
                    "inventing a time or timezone."
                ),
            )
        date_relation = (
            "is the current calendar date"
            if deadline_state.deadline.date == now.date()
            else "is earlier than the current calendar date"
        )
        return DeadlinePassResult(
            status=DeadlinePassStatus.UNCERTAIN,
            reason=(
                f"The resolved deadline date {date_relation}, but its time or "
                "timezone is missing, local/unspecified, invalid, or ambiguous; "
                "no end-of-day or timezone assumption is permitted."
            ),
        )
    if now.astimezone(UTC) >= deadline_at.astimezone(UTC):
        return DeadlinePassResult(
            status=DeadlinePassStatus.PASSED,
            reason="Current time is at or after the fully specified deadline.",
        )
    return DeadlinePassResult(
        status=DeadlinePassStatus.NOT_PASSED,
        reason="Current time is before the fully specified deadline.",
    )
