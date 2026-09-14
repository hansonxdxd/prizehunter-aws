"""Independent contracts for the extracted domain, without importing the app."""
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from prizehunter_core.competition_intelligence import (
    CompetitionIntelligence, ResolutionStatus, resolve_field_claims,
)
from prizehunter_core.deadlines import DeadlineAdapterStatus, adapt_deadline
from prizehunter_core.eligibility import EligibilityStatus, evaluate_hard_eligibility
from prizehunter_core.schemas import CompetitionRecord
from prizehunter_core.user_profile import UserProfile

ROOT = Path(__file__).resolve().parents[2]


def test_core_imports_without_provider_or_app():
    result = subprocess.run([sys.executable, '-c', '''
import importlib, importlib.abc, pkgutil, sys
class RejectOuter(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'app', 'google', 'httpx', 'fastapi', 'dotenv', 'boto3'}:
            raise AssertionError('Core imported outer dependency: ' + fullname)
sys.meta_path.insert(0, RejectOuter())
import prizehunter_core
for module in pkgutil.iter_modules(prizehunter_core.__path__):
    importlib.import_module('prizehunter_core.' + module.name)
'''], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_explicit_blocker_wins_over_missing_facts():
    record = CompetitionRecord(geographic_restrictions=['Open only to legal residents of Canada.'])
    result = evaluate_hard_eligibility(record, UserProfile(profile_id='personal', version=1, country='Taiwan'))
    assert result.status is EligibilityStatus.INELIGIBLE
    assert any(c.status is EligibilityStatus.UNCERTAIN for c in result.checks)


def test_missing_rules_are_unknown_not_eligible():
    result = evaluate_hard_eligibility(CompetitionRecord(), UserProfile(profile_id='personal', version=1))
    assert result.status is EligibilityStatus.UNCERTAIN
    assert all(c.status is EligibilityStatus.UNCERTAIN for c in result.checks)


def test_fixture_conflicts_preserve_provenance_and_block_legacy_fallback():
    payload = json.loads((ROOT / 'tests/fixtures/claim_conflicts.json').read_text())
    # Fixture shapes and expected resolutions are exercised by existing integration tests.
    cases = payload['cases']
    checked = 0
    for case in cases.values():
        intelligence = CompetitionIntelligence.model_validate_json(json.dumps(case['competition_intelligence']))
        if case['expected_status'] != 'unresolved_conflict':
            continue
        resolved = resolve_field_claims(intelligence.claims, resolved_at=datetime(2026, 8, 28, tzinfo=UTC))
        assert resolved.resolution_status is ResolutionStatus.UNRESOLVED_CONFLICT
        assert resolved.effective_value is None
        intelligence = CompetitionIntelligence(
            competition_id=intelligence.competition_id,
            claims=intelligence.claims,
            resolved_fields=[resolved],
        )
        state = adapt_deadline(competition_record=CompetitionRecord(deadline='2099-01-01'), intelligence=intelligence, field_path=resolved.field_path, scope=resolved.scope)
        assert state.status is DeadlineAdapterStatus.UNRESOLVED_CONFLICT
        assert set(state.claim_ids) == set(resolved.conflicting_claim_ids)
        checked += 1
    assert checked >= 1
