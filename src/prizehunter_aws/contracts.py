"""Transport contracts only. Decision rules remain in the pinned Core."""

from datetime import datetime
from typing import Literal

from prizehunter_core.eligibility_claims import EligibilityClaimBatch
from prizehunter_core.fit_evaluation import FitPreferences
from prizehunter_core.schemas import CompetitionRecord
from prizehunter_core.user_profile import UserProfile
from pydantic import BaseModel, ConfigDict, Field


class ResearchDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record: CompetitionRecord
    claims: EligibilityClaimBatch


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal_id: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=2000)
    profile: UserProfile
    preferences: FitPreferences


class SearchCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    title: str
    snippet: str
    # A search hit is a pointer, never official evidence.
    evidence_status: Literal["discovery_only"] = "discovery_only"


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    provider: str
    status: Literal["ok", "unavailable", "error", "replay"]
    candidates: list[SearchCandidate] = Field(default_factory=list)
    reason: str | None = None
    observed_at: datetime
