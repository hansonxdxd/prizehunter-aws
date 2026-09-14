"""Source-scoped claim acceptance independent of retrieval/model providers."""
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from prizehunter_core.competition_intelligence import ResolutionStatus
from prizehunter_core.evidence import CompetitionEvidenceBundle
from prizehunter_core.eligibility_claims import EligibilityClaimBatch, validate_claim_drafts

NOW = datetime(2026, 8, 28, tzinfo=UTC)


def bundle():
    sources = []
    for index, text in enumerate(['Teams of 1 to 4 may enter.', 'Teams of 2 to 5 may enter.']):
        sources.append({
            'source_id': f'src_{index:012x}', 'source_url': f'https://example.com/rules/{index}',
            'source_type': 'rules', 'content_type': 'html', 'authority_hint': 'organizer_controlled',
            'relation_to_seed': 'seed' if index == 0 else 'same_origin',
            'retrieved_at': NOW.isoformat(), 'extraction_status': 'success',
            'extracted_text': text, 'content_sha256': 'a' * 64,
            'metadata': {'depth': index, 'retrieval_method': 'local-test-retriever'},
        })
    return CompetitionEvidenceBundle.model_validate_json(json.dumps({
        'seed_url': sources[0]['source_url'], 'started_at': NOW.isoformat(),
        'completed_at': NOW.isoformat(), 'sources': sources,
    }))


def batch():
    return EligibilityClaimBatch.model_validate({'claims': [{
        'field_path': '/eligibility/team_size',
        'value_json': json.dumps({'minimum_team_size': index + 1, 'maximum_team_size': index + 4, 'solo_allowed': index == 0, 'teams_allowed': True}),
        'source_id': source.source_id, 'evidence_text': source.extracted_text, 'confidence': 0.99,
    } for index, source in enumerate(bundle().sources)]})


def test_non_google_retrieval_metadata_round_trips():
    evidence = bundle()
    assert CompetitionEvidenceBundle.model_validate_json(evidence.model_dump_json()) == evidence
    assert evidence.sources[0].metadata.retrieval_method == 'local-test-retriever'
    broken = evidence.model_dump(mode='json')
    broken['sources'][0]['content_sha256'] = None
    with pytest.raises(ValidationError):
        CompetitionEvidenceBundle.model_validate_json(json.dumps(broken))


def test_confident_conflicting_drafts_remain_unresolved():
    result = validate_claim_drafts(batch(), bundle(), competition_id='shared', observed_at=NOW)
    assert not result.rejected_claims
    field = result.intelligence.resolved_fields[0]
    assert field.resolution_status is ResolutionStatus.UNRESOLVED_CONFLICT
    assert field.effective_value is None
    assert len(field.conflicting_claim_ids) == 2
    assert {c.evidence_locator for c in result.intelligence.claims} == {s.source_id for s in bundle().sources}


def test_cross_source_excerpt_is_rejected_not_promoted_to_fact():
    drafts = batch()
    drafts.claims[0].evidence_text = bundle().sources[1].extracted_text
    result = validate_claim_drafts(drafts, bundle(), competition_id='shared', observed_at=NOW)
    assert len(result.rejected_claims) == 1
    assert result.rejected_claims[0].source_id == bundle().sources[0].source_id
    assert len(result.intelligence.claims) == 1
