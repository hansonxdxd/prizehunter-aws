"""New, explicitly synthetic round-one fixtures. No historical raw traces."""

import copy
import json
from datetime import UTC, datetime

from prizehunter_core.evidence import CompetitionEvidenceBundle

from .contracts import Goal
from .retrieval import make_source
from .runtime import ReplayModel, ReplayStep, ResearchTools, StrandsRuntime

NOW = datetime(2026, 9, 13, 8, tzinfo=UTC)
URL = "https://example.com/synthetic-rules"


def scenario(country="Canada", revision=1):
    deadline = "2099-09-14T17:00:00-07:00" if revision == 1 else "2099-09-20T17:00:00-07:00"
    lines = [
        "SYNTHETIC Opportunity Watch Challenge",
        "Open only to legal residents of Canada.",
        "Build a working prototype and submit a demo video.",
        f"Submission deadline: {deadline}.",
    ]
    source = make_source(
        URL,
        text="\n".join(lines),
        official=True,
        now=NOW,
        retrieval_method="offline-synthetic-v1",
        warnings=["Synthetic fixture, not a real competition"],
    )
    bundle = CompetitionEvidenceBundle.model_validate_json(
        json.dumps(
            {
                "seed_url": URL,
                "started_at": NOW.isoformat(),
                "completed_at": NOW.isoformat(),
                "sources": [source.model_dump(mode="json")],
            }
        )
    )
    goal = Goal.model_validate_json(
        json.dumps(
            {
                "goal_id": "synthetic-watch",
                "description": "Find prototype opportunities and watch rule changes.",
                "profile": {
                    "profile_id": "synthetic-" + country.lower(),
                    "version": 1,
                    "country": country,
                    "skills": ["Python"],
                },
                "preferences": {
                    "preferences_id": "synthetic-preferences",
                    "version": 1,
                    "available_hours_before_deadline": 12,
                    "strategic_goals": ["Build a portfolio prototype"],
                },
            }
        )
    )
    record = {
        "competition_name": lines[0],
        "source_url": URL,
        "deadline": deadline,
        "geographic_restrictions": [lines[1]],
        "submission_requirements": [lines[2]],
        "source_evidence": [
            {"field": field, "excerpt": quote}
            for field, quote in [
                ("competition_name", lines[0]),
                ("geographic_restrictions", lines[1]),
                ("submission_requirements", lines[2]),
                ("deadline", lines[3]),
            ]
        ],
        "uncertainties": [
            {
                "field": "eligibility",
                "reason": "Other eligibility requirements are unknown in this synthetic evidence.",
            }
        ],
    }
    draft = {
        "record": record,
        "claims": {
            "claims": [
                {
                    "field_path": "/eligibility/residence",
                    "value_json": json.dumps({"mode": "allowed_countries", "allowed_countries": ["Canada"]}),
                    "source_id": source.source_id,
                    "evidence_text": lines[1],
                    "confidence": 0.99,
                }
            ],
            "uncertainties": ["Age, team, and other requirements need verification."],
        },
    }
    reference = {"source_id": source.source_id, "excerpt": lines[2]}
    dimension = {
        "rating": "medium",
        "score": 60,
        "explanation": "Synthetic replay rating, not model quality evidence.",
        "confidence": 0.5,
        "competition_evidence": [reference],
        "input_refs": ["preferences_goals"],
    }
    fit = {
        "recommendation": "go",
        "overall_score": 60,
        "confidence": 0.5,
        "dimensions": {
            key: copy.deepcopy(dimension)
            for key in [
                "skill_capability",
                "build_feasibility",
                "time_effort",
                "reward_attractiveness",
                "participation_burden",
                "strategic_interest",
            ]
        },
        "effort_estimate": {
            "level": "medium",
            "minimum_hours": 4.0,
            "maximum_hours": 8.0,
            "confidence": 0.5,
            "drivers": ["Synthetic prototype exercise"],
            "competition_evidence": [reference],
            "input_refs": ["preferences_available_hours"],
        },
        "why": [
            {
                "text": "Synthetic portfolio exercise.",
                "competition_evidence": [reference],
                "input_refs": ["preferences_goals"],
            }
        ],
        "uncertainties": ["Synthetic model output only"],
    }
    plan = {
        "objective": "Verify requirements before deciding whether to prepare a submission.",
        "actions": [
            {
                "id": "action_verify_rules",
                "title": "Verify remaining eligibility rules",
                "reason": "Eligibility remains uncertain.",
                "kind": "verification",
                "basis": "verification",
                "priority": "high",
                "effort": {"minimum_hours": 0.25, "maximum_hours": 1.0},
                "timing": "Before deciding",
                "evidence": [],
                "refs": ["eligibility_uncertainties"],
                "depends_on": [],
                "human_confirmation": True,
                "uncertainty": "Missing eligibility rules",
                "confirm_at": "Ask the organizer using a verified official contact",
            }
        ],
        "sequence": ["action_verify_rules"],
        "unresolved": ["Verify unknown requirements; no message is sent automatically."],
    }
    return goal, bundle, {"research": draft, "fit": fit, "plan": plan}


def replay_runtime(bundle, drafts):
    steps = [ReplayStep("read_evidence", {"url": str(s.source_url)}) for s in bundle.sources]
    steps += [
        ReplayStep("ResearchDraftResponse", {"payload": drafts["research"]}, "read_evidence"),
        ReplayStep("FitEvaluationDraftResponse", {"payload": drafts["fit"]}),
        ReplayStep("ActionPlanDraftResponse", {"payload": drafts["plan"]}),
    ]
    return StrandsRuntime(ReplayModel(steps), ResearchTools(bundle=bundle))
