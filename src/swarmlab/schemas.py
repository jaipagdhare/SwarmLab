from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentAction(StrictModel):
    robot_id: Literal["a", "b", "c"]
    operation: Literal["move", "observe", "wait"]
    direction: Literal["north", "south", "east", "west"] | None = None

    @model_validator(mode="after")
    def check_direction(self):
        if self.operation == "move" and self.direction is None:
            raise ValueError("move requires direction")
        if self.operation != "move" and self.direction is not None:
            raise ValueError("Only move accepts direction")
        return self


class RobotAssignment(StrictModel):
    robot_id: Literal["a", "b", "c"]
    task: str = Field(max_length=200)
    maintain_until: str = Field(max_length=200)


class Decision(StrictModel):
    explanation: str = Field(max_length=500, description="Brief action rationale, not private reasoning")
    action: AgentAction
    assignments: list[RobotAssignment] = Field(default_factory=list, max_length=3, description="Update explicit robot tasks and conditions to preserve; empty keeps previous assignments.")


class ObservedFact(StrictModel):
    observation_id: str
    phase: Literal["before", "after"]
    object_id: str
    property: Literal["active", "open", "acting_robot_on_object"]
    value: bool


class Hypothesis(StrictModel):
    local_id: str = Field(pattern=r"^h[0-9]+$", description="Local identifier: h1, h2, h3, etc. Procedures must reference these exact IDs.")
    description: str = Field(min_length=1, max_length=1000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    unresolved_questions: list[str] = Field(max_length=10)
    observed_facts: list[ObservedFact] = Field(default_factory=list, max_length=20, description="Facts checked against cited local observations. Include acting_robot_on_object and active facts for switch occupancy claims.")


class Procedure(StrictModel):
    title: str = Field(min_length=1, max_length=150)
    hypothesis_ids: list[str] = Field(min_length=1, max_length=10)
    roles: list[str] = Field(min_length=1, max_length=3)
    preconditions: list[str] = Field(min_length=1, max_length=10)
    steps: list[str] = Field(min_length=1, max_length=12)
    expected_observations: list[str] = Field(min_length=1, max_length=10)
    status: Literal["candidate"]
    ongoing_conditions: list[str] = Field(default_factory=list, max_length=6, description="Conditions that must remain true throughout execution, based on evidence; state unknowns explicitly.")


class SleepArtifact(StrictModel):
    outcome: Literal["candidates", "insufficient_evidence"]
    summary: str = Field(min_length=1, max_length=1500)
    hypotheses: list[Hypothesis] = Field(max_length=5)
    procedures: list[Procedure] = Field(max_length=3)

    @model_validator(mode="after")
    def check_links(self):
        ids = [h.local_id for h in self.hypotheses]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate local hypothesis IDs")
        if any(not set(p.hypothesis_ids).issubset(ids) for p in self.procedures):
            raise ValueError("Procedure references an unknown hypothesis")
        if self.outcome == "insufficient_evidence" and self.procedures:
            raise ValueError("Insufficient evidence cannot produce a procedure")
        if self.outcome == "candidates" and not self.hypotheses:
            raise ValueError("Candidate output needs evidence-linked hypotheses")
        return self

    def validate_evidence(self, observations: list[dict]):
        available = {item["id"] for item in observations}
        for hypothesis in self.hypotheses:
            if not set(hypothesis.evidence_ids).issubset(available):
                raise ValueError("Hypothesis cites evidence outside the discovery snapshot")



def validate_observed_facts(artifact, observations):
    """Check factual premises against sensor data, never action explanations or private world state."""
    indexed = {o['id']: o for o in observations}
    for hypothesis in artifact.hypotheses:
        if not hypothesis.observed_facts:
            raise ValueError('Each hypothesis requires observed_facts from its cited observations')
        for fact in hypothesis.observed_facts:
            if fact.observation_id not in hypothesis.evidence_ids or fact.observation_id not in indexed:
                raise ValueError('Observed fact must reference evidence cited by its hypothesis')
            view = indexed[fact.observation_id].get(fact.phase, {})
            obj = next((o for o in view.get('objects', []) if o.get('id') == fact.object_id), None)
            if obj is None:
                raise ValueError('Observed fact refers to an object absent from the cited view')
            if fact.property == 'acting_robot_on_object':
                actual = tuple(view.get('position', [])) == tuple(obj['position'])
            else:
                actual = obj.get(fact.property)
            if not isinstance(actual, bool) or actual != fact.value:
                raise ValueError('Observed fact contradicts the cited sensor observation')
