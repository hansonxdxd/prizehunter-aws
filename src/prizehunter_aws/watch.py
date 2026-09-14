"""Single-user local run-once diff. No recurring trigger or notifications."""

import hashlib
import json
import os
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def run_once(result, state_path):
    path = Path(state_path)
    goal = result["goal"]
    identity = digest(goal)
    current = {
        "record": result["record"],
        "evidence": [
            {"url": s["source_url"], "hash": s["content_sha256"], "status": s["extraction_status"]}
            for s in result["evidence"]["sources"]
        ],
        "eligibility": result["eligibility"]["overall_status"],
        "recommendation": result["fit"]["recommendation"],
    }
    state = (
        json.loads(path.read_text())
        if path.exists()
        else {"version": 1, "goal_hash": identity, "goal": goal, "opportunities": {}}
    )
    if state.get("version") != 1 or state.get("goal_hash") != identity:
        raise ValueError("Watch state belongs to a different goal/profile; use a separate state file")
    key = result["competition_id"]
    previous = state["opportunities"].get(key)
    failed = any(s["status"] != "success" for s in current["evidence"])
    if failed:
        # Preserve last good baseline. A fetch failure is not a deletion or rule change.
        return {
            "status": "retrieval_failed",
            "pending_decisions": [],
            "baseline_updated": False,
            "reason": "Unable to compare rules; last good evidence retained",
        }
    if previous is None:
        event = {"kind": "new_opportunity", "competition_id": key, "current": current}
    elif previous != current:
        event = {
            "kind": "changed",
            "competition_id": key,
            "previous": previous,
            "current": current,
            "changed_fields": [field for field in current if previous.get(field) != current[field]],
        }
    else:
        event = None
    state["opportunities"][key] = current
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    os.replace(temporary, path)
    return {
        "status": "changed" if event else "unchanged",
        "pending_decisions": [event] if event else [],
        "baseline_updated": True,
        "recurring_trigger_configured": False,
    }
