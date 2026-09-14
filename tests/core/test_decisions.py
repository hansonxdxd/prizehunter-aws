"""The shared decision policy accepts a non-Google structured generator."""
import copy
import importlib
import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from prizehunter_core.action_planner import ActionPlan

REPLAY = json.loads((Path(__file__).parents[1] / 'fixtures/google_contract_replay.json').read_text())
MODEL = 'local-structured-v1'


def neutral(payload):
    result = copy.deepcopy(payload)
    if 'gemini_skipped' in result:
        result['inference_skipped'] = result.pop('gemini_skipped')
    if result.get('model') is not None:
        result['model'] = MODEL
    return result


def inputs_for(case):
    inputs = copy.deepcopy(case['inputs'])
    for key, module, cls in [
        ('record', 'schemas', 'CompetitionRecord'),
        ('intelligence', 'competition_intelligence', 'CompetitionIntelligence'),
        ('evidence_bundle', 'evidence', 'CompetitionEvidenceBundle'),
        ('eligibility', 'eligibility_assessment_v3', 'EligibilityAssessmentV3'),
        ('profile', 'user_profile', 'UserProfile'),
        ('preferences', 'fit_evaluation', 'FitPreferences'),
        ('fit', 'fit_evaluation', 'FitEvaluation'),
    ]:
        if key in inputs:
            model = getattr(importlib.import_module('prizehunter_core.' + module), cls)
            inputs[key] = model.model_validate_json(json.dumps(neutral(inputs[key])))
    inputs['generated_at'] = datetime.fromisoformat(inputs['generated_at'])
    return inputs


def function_for(case):
    module, name = ('fit_evaluation', 'evaluate_fit') if case['kind'] == 'fit' else ('action_planner', 'plan_actions')
    return getattr(importlib.import_module('prizehunter_core.' + module), name)


@pytest.mark.parametrize('case', REPLAY['cases'], ids=[f"{c['kind']}-{c['output'].get('recommendation', c['output'].get('recommendation_reference'))}" for c in REPLAY['cases']])
def test_independent_provider_preserves_shared_decisions(case):
    calls = []

    def generator(prompt, schema):
        index = len(calls)
        assert index < len(case['calls']), 'Stopped outcomes must make zero inference calls'
        calls.append(prompt)
        return schema.model_validate_json(json.dumps(case['calls'][index]['draft'])), None

    result, _ = function_for(case)(**inputs_for(case), generator=generator, model=MODEL)
    assert result.model_dump(mode='json') == neutral(case['output'])
    assert len(calls) == len(case['calls'])
    if case['kind'] == 'plan':
        assert result.external_actions_executed is False
        invalid = result.model_dump(mode='json')
        invalid['external_actions_executed'] = True
        with pytest.raises(ValidationError):
            ActionPlan.model_validate_json(json.dumps(invalid))


@pytest.mark.parametrize('kind', ['fit', 'plan'])
def test_invented_source_excerpt_fails_after_one_correction(kind):
    case = next(c for c in REPLAY['cases'] if c['kind'] == kind and c['calls'])
    draft = copy.deepcopy(case['calls'][0]['draft'])
    if kind == 'fit':
        draft['why'][0]['competition_evidence'][0]['excerpt'] = 'Invented organizer permission'
    else:
        action = next(a for a in draft['actions'] if a['competition_evidence'])
        action['competition_evidence'][0]['excerpt'] = 'Invented organizer permission'
    prompts = []

    def generator(prompt, schema):
        prompts.append(prompt)
        return schema.model_validate_json(json.dumps(draft)), None

    with pytest.raises(ValueError, match='excerpt is not present'):
        function_for(case)(**inputs_for(case), generator=generator, model=MODEL)
    assert len(prompts) == 2
    assert 'VALIDATION FEEDBACK FROM THE APPLICATION' in prompts[1]
