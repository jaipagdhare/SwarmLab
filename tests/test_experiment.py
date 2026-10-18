from swarmlab import experiment
from swarmlab.awake import Budget
import pytest


class FrozenMemory:
    def get_artifact(self, artifact_id):
        return {'artifact_digest': 'frozen-digest', 'metadata': {'usage': {'output_tokens': 40}}}


def test_paired_evaluation_keeps_failed_attempts_and_exports(monkeypatch, tmp_path):
    monkeypatch.setattr(experiment, 'ROOT', tmp_path)
    monkeypatch.setattr(experiment, 'save_run', lambda run: None)
    calls = []
    def transfer(memory, model, **kwargs):
        calls.append((kwargs['seed'], kwargs['condition']))
        if kwargs['condition'] == 'raw':
            raise RuntimeError('private failure details')
        return {'result': {'seed': kwargs['seed'], 'condition': kwargs['condition'],
                           'success': False, 'termination': 'action_budget_exhausted'}}
    monkeypatch.setattr(experiment, 'transfer', transfer)
    model = type('Model', (), {'name': 'test-double-only'})()
    result = experiment.evaluate(FrozenMemory(), model, artifact_id='frozen', seeds=[101,102], budget=Budget(max_actions=4))
    assert set(calls) == {(s,c) for s in [101,102] for c in ['none','raw','sleep']}
    assert len(result['results']) == 6
    assert sum(r['termination']=='infrastructure_error' for r in result['results']) == 2
    assert result['artifact_digest'] == 'frozen-digest'
    assert result['sleep_usage'] == {'output_tokens':40}
    assert result['sleep_amortized_over_missions'] == 2
    assert len(list((tmp_path/'outputs'/'runs').glob('*.csv'))) == 1
    assert 'private failure' not in str(result)


def test_repeated_seeds_rejected():
    with pytest.raises(ValueError, match='distinct'):
        experiment.evaluate(FrozenMemory(), None, artifact_id='frozen', seeds=[1,1])


class LocalMemory:
    def get_local_rule(self):
        return {'id':'localrule-frozen','status':'contradicted','scope':'two-switch benchmark',
                'table':{'00':False},'missing_cases':['01','10'],'contradictions':['11'],
                'training_seeds':[11,101]}
    def retrieve_local_memory(self, rule_id=None):
        assert rule_id=='localrule-frozen'
        return {'rule':self.get_local_rule(),'evidence':[{'observation_id':'obs-real','occupancy_bits':'11','gate_open':True},
                                                       {'observation_id':'obs-counter','occupancy_bits':'11','gate_open':False}]}
    def get_artifact(self, artifact_id):
        raise AssertionError('Local learning must not require a sleep artifact')


def test_local_rule_context_preserves_contradictions_and_omits_training_seeds():
    context=experiment.prepare_context(LocalMemory(),'local_rule','localrule-frozen')
    local=context['local_learning']
    assert local['status']=='contradicted'
    assert local['contradictions']==['11']
    assert len(local['evidence'])==2
    assert 'training_seeds' not in local
    assert experiment.prepare_context(LocalMemory(),'none','')=={}
    with pytest.raises(ValueError,match='budget'):
        experiment.prepare_context(LocalMemory(),'local_rule','localrule-frozen',max_chars=10)


def test_gemini_transfer_freezes_local_rule_without_sleep(monkeypatch):
    captured={}
    def awake(memory,model,**kwargs):
        captured.update(kwargs)
        return {'result':{'model_calls':0}}
    monkeypatch.setattr(experiment,'run_awake',awake)
    experiment.transfer(LocalMemory(),None,seed=705,condition='local_rule')
    assert captured['local_rule_id']=='localrule-frozen'
    assert captured['artifact_id']==''
    assert captured['historical_context']['local_learning']['rule_id']=='localrule-frozen'
    with pytest.raises(ValueError,match='fresh seed'):
        experiment.transfer(LocalMemory(),None,seed=101,condition='local_rule')
