import pytest
from pydantic import ValidationError

from swarmlab.schemas import AgentAction, SleepArtifact


def candidate():
    return {"outcome": "candidates", "summary": "A possible relationship was observed.",
            "hypotheses": [{"local_id": "h1", "description": "A switch might affect a gate.",
                            "evidence_ids": ["obs1"], "unresolved_questions": ["Is occupancy sufficient?"]}],
            "procedures": [{"title": "Investigate", "hypothesis_ids": ["h1"], "roles": ["observer"],
                            "preconditions": ["Switch visible"], "steps": ["Observe the switch"],
                            "expected_observations": ["Switch state"], "status": "candidate"}]}


def test_out_of_snapshot_evidence_rejected():
    artifact = SleepArtifact.model_validate(candidate())
    with pytest.raises(ValueError, match="outside"):
        artifact.validate_evidence([{"id": "different_episode_obs"}])
    artifact.validate_evidence([{"id": "obs1"}])


def test_broken_hypothesis_link_rejected():
    value = candidate()
    value["procedures"][0]["hypothesis_ids"] = ["h404"]
    with pytest.raises(ValidationError):
        SleepArtifact.model_validate(value)


def test_model_cannot_promote_its_own_hypothesis():
    value = candidate()
    value["procedures"][0]["status"] = "verified"
    with pytest.raises(ValidationError):
        SleepArtifact.model_validate(value)


def test_insufficient_evidence_is_valid_but_cannot_publish_procedure():
    value = candidate()
    value["outcome"] = "insufficient_evidence"
    with pytest.raises(ValidationError):
        SleepArtifact.model_validate(value)
    value["procedures"] = []
    SleepArtifact.model_validate(value)


def test_invalid_move_and_unknown_action_rejected():
    with pytest.raises(ValidationError):
        AgentAction.model_validate({"operation": "move", "robot_id": "a"})
    with pytest.raises(ValidationError):
        AgentAction.model_validate({"operation": "reveal_map", "robot_id": "a"})



def test_sensor_facts_reject_claimed_arrival_after_blocked_move():
    from swarmlab.schemas import validate_observed_facts
    value = candidate()
    value['hypotheses'][0]['observed_facts'] = [
        {'observation_id':'obs1','phase':'after','object_id':'switch_1',
         'property':'acting_robot_on_object','value':True}]
    observations = [{'id':'obs1','outcome':'blocked_wall','explanation':'I reached the switch',
                     'after':{'position':[1,2], 'objects':[{'id':'switch_1','position':[2,2],'active':False}]}}]
    with pytest.raises(ValueError, match='contradicts'):
        validate_observed_facts(SleepArtifact.model_validate(value), observations)
    value['hypotheses'][0]['observed_facts'][0]['value'] = False
    validate_observed_facts(SleepArtifact.model_validate(value), observations)


def test_sensor_facts_reject_invented_switch_state_and_missing_premises():
    from swarmlab.schemas import validate_observed_facts
    value = candidate()
    observations = [{'id':'obs1','after':{'position':[2,2], 'objects':[{'id':'switch_1','position':[2,2],'active':True}]}}]
    with pytest.raises(ValueError, match='requires'):
        validate_observed_facts(SleepArtifact.model_validate(value), observations)
    value['hypotheses'][0]['observed_facts'] = [
        {'observation_id':'obs1','phase':'after','object_id':'switch_1','property':'active','value':False}]
    with pytest.raises(ValueError, match='contradicts'):
        validate_observed_facts(SleepArtifact.model_validate(value), observations)
    value['hypotheses'][0]['observed_facts'][0]['value'] = True
    validate_observed_facts(SleepArtifact.model_validate(value), observations)
