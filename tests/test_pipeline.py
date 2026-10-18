from copy import deepcopy
import pytest

from swarmlab.awake import Budget, run_awake
from swarmlab.model import Completion
from swarmlab.sleep import run_sleep


class TestMemory:
    __test__ = False

    def __init__(self):
        self.episode = None
        self.published = None

    def register_policy(self, version, prompt):
        return version

    def link_policy(self, episode_id, policy_id):
        self.policy_id = policy_id

    def create_episode(self, seed, kind, condition, artifact_id):
        self.episode = {"id": "episode-test", "kind": kind, "status": "running", "observations": []}
        return self.episode["id"]

    def record_context(self, episode_id, context):
        self.initial = deepcopy(context)

    def append_experience(self, episode_id, event):
        obs_id = f"obs-{len(self.episode['observations'])}"
        self.episode["observations"].append({"id": obs_id, **deepcopy(event)})
        return obs_id

    def finish_episode(self, episode_id, result):
        self.episode["status"] = result["termination"]
        self.episode["result"] = result

    def get_episode(self, episode_id):
        return deepcopy(self.episode)

    def publish_sleep_artifact(self, episode_id, artifact, metadata):
        self.published = {"artifact": artifact, "metadata": metadata}
        return self.published


class TestModel:
    __test__ = False
    name = "test-double-only"

    def __init__(self, response=None, failure=False):
        self.contexts = []
        self.response = response or {"explanation": "Inspect current surroundings", "action": {"operation": "observe", "robot_id": "a"}}
        self.failure = failure

    def complete(self, **kwargs):
        self.contexts.append(deepcopy(kwargs["context"]))
        if self.failure:
            raise RuntimeError("test failure")
        return Completion(deepcopy(self.response), {"input_tokens": 10, "output_tokens": 5}, 0.01)


def test_awake_budget_and_no_private_state_leak():
    memory, model = TestMemory(), TestModel()
    result = run_awake(memory, model, seed=918273, budget=Budget(max_actions=5))
    assert result["result"]["actions"] == 5
    assert result["result"]["model_calls"] == 2
    assert len(memory.episode["observations"]) == 5
    assert all("918273" not in str(c) and "evaluator_snapshot" not in str(c) for c in model.contexts)
    assert memory.episode["status"] == "discovery_budget_complete"


def test_model_failure_is_an_explicit_result():
    memory, model = TestMemory(), TestModel(failure=True)
    result = run_awake(memory, model, seed=1)
    assert result["result"]["termination"] == "model_error"
    assert result["result"]["model_calls"] == 1
    assert memory.episode["status"] == "model_error"


def test_sleep_receives_only_observations_and_allows_abstention():
    memory = TestMemory()
    run_awake(memory, TestModel(), seed=123, budget=Budget(max_actions=4))
    model = TestModel(response={"outcome": "insufficient_evidence", "summary": "No relationship established.",
                                "hypotheses": [], "procedures": []})
    artifact = run_sleep(memory, model, "episode-test")
    assert set(model.contexts[0]) == {"observations"}
    assert artifact["artifact"]["outcome"] == "insufficient_evidence"


def test_no_memory_condition_cannot_be_given_history():
    with pytest.raises(ValueError, match="No-memory"):
        run_awake(TestMemory(), TestModel(), seed=1, condition="none", historical_context={"answer": "secret"})



def test_cancel_during_model_call_records_usage_without_next_action():
    stopped = False
    class CancellingModel(TestModel):
        def complete(self, **kwargs):
            nonlocal stopped
            result = super().complete(**kwargs)
            stopped = True
            return result
    result = run_awake(TestMemory(), CancellingModel(), seed=1, cancelled=lambda: stopped)
    assert result['result']['termination'] == 'cancelled'
    assert result['result']['actions'] == 3
    assert result['result']['model_calls'] == 1
    assert result['result']['usage_complete'] is True


def test_sleep_normalizes_labels_and_links_without_changing_evidence():
    from swarmlab.sleep import normalize_hypothesis_ids
    value = {'hypotheses':[{'local_id':'hypothesis_1','evidence_ids':['obs-real']}],
             'procedures':[{'hypothesis_ids':['hypothesis_1']}]}
    result = normalize_hypothesis_ids(value)
    assert result['hypotheses'][0]['local_id'] == 'h1'
    assert result['procedures'][0]['hypothesis_ids'] == ['h1']
    assert result['hypotheses'][0]['evidence_ids'] == ['obs-real']
    assert value['hypotheses'][0]['local_id'] == 'hypothesis_1'
    value['procedures'][0]['hypothesis_ids'] = ['unknown']
    assert normalize_hypothesis_ids(value) == value


def test_invalid_sleep_retains_usage_and_safe_field_details():
    from swarmlab.sleep import validate_sleep_completion
    from swarmlab.model import ModelError
    with pytest.raises(ModelError) as error:
        validate_sleep_completion(Completion({'outcome':'bad'}, {'input_tokens':10}, 1), [])
    assert error.value.code == 'invalid_sleep_artifact'
    assert error.value.usage == {'input_tokens':10}
    assert error.value.validation_errors
    assert all('input' not in e for e in error.value.validation_errors)


def test_local_rule_reaches_model_and_provenance_is_recorded():
    memory,model=TestMemory(),TestModel()
    links=[]
    memory.link_local_rule_use=lambda episode,rule:links.append((episode,rule))
    context={'local_learning':{'rule_id':'rule-frozen','table':{'11':True},'status':'validated_in_scope'}}
    run=run_awake(memory,model,seed=705,kind='evaluation',condition='local_rule',
                  historical_context=context,local_rule_id='rule-frozen',budget=Budget(max_actions=4))
    assert model.contexts[0]['historical_memory']==context
    assert memory.initial['initial_context']['historical_memory']==context
    assert links==[('episode-test','rule-frozen')]
    assert run['result']['local_rule_id']=='rule-frozen'
