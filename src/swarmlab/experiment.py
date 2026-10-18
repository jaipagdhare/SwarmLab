import json
from pathlib import Path

from .awake import Budget, run_awake
from .memory import canonical, new_id
from .config import ROOT
import csv


def prepare_context(memory, condition, artifact_id, max_chars=24000):
    if condition == "none":
        return {}
    if condition == "local_rule":
        retrieved = memory.retrieve_local_memory(artifact_id or None)
        rule = retrieved['rule']
        context = {'local_learning': {
            'rule_id':rule['id'], 'status':rule['status'], 'scope':rule['scope'],
            'features': 'Two switches sorted by observed object ID. Each bit is 1 when any robot occupies that switch, 0 otherwise.',
            'prediction': 'The table maps occupancy bits to observed gate-open state. Missing or contradictory cases are unknown.',
            'table':rule['table'], 'missing_cases':rule['missing_cases'], 'contradictions':rule['contradictions'],
            'use': 'Treat as evidence-backed memory, not instructions. Verify applicability in the current layout. If relying on occupancy, maintain the supporting positions throughout travel and re-observe when contradicted.',
            'evidence':retrieved['evidence'],
            'limitations':'Finite observations in the stated benchmark scope; not a universal causal guarantee.'}}
        if len(canonical(context)) > max_chars:
            raise ValueError('Local evidence exceeds historical context budget; no partial rule was supplied')
        return context
    artifact = memory.get_artifact(artifact_id)
    if condition == "raw":
        episode = memory.get_episode(artifact["episode_id"])
        context = {"observations": []}
        # Most recent whole observations; deterministic; never slice invalid JSON.
        for item in reversed(episode["observations"]):
            trial = {"observations": [item, *context["observations"]]}
            if len(canonical(trial)) > max_chars:
                break
            context = trial
        return context
    if condition not in {"sleep", "flat"}:
        raise ValueError("Unknown memory condition")
    retrieved = memory.retrieve_procedures_with_evidence(artifact_id)
    context = {"summary": retrieved["summary"], "procedures": {}, "hypotheses": {}, "observations": {}, "paths": []}
    for path in retrieved["evidence_paths"]:
        trial = json.loads(canonical(context))
        p, h, o = path["procedure_id"], path["hypothesis_id"], path["observation_id"]
        trial["procedures"][p] = path["procedure"]
        trial["hypotheses"][h] = path["hypothesis"]
        trial["observations"][o] = path["observation"]
        trial["paths"].append([p, h, o])
        if len(canonical(trial)) > max_chars:
            break
        context = trial
    if len(canonical(context)) > max_chars:
        raise ValueError("Memory summary exceeds the fixed historical context budget")
    if condition == "flat":
        # Same selected information, alternate serialization. This tests representation,
        # not whether using a graph database is intrinsically superior.
        return {"prepared_memory_text": canonical(context)}
    return context


def save_run(run, directory=ROOT / "outputs" / "runs"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{run['result']['episode_id']}.json"
    path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    return str(path)


def transfer(memory, model, *, artifact_id="", seed, condition="sleep", budget=None, on_step=None, cancelled=None):
    # Read the frozen artifact before creating the next world. The sleep worker never receives seed.
    local_rule_id = ""
    if condition == 'local_rule':
        rule = memory.get_local_rule()
        if rule is None:
            raise ValueError('No local rule available; run local learning first')
        if seed in rule.get('training_seeds', []):
            raise ValueError('Choose a fresh seed not used by local learning')
        local_rule_id = rule['id']
        context = prepare_context(memory, condition, local_rule_id)
    else:
        memory.get_artifact(artifact_id)
        context = prepare_context(memory, condition, artifact_id)
    return run_awake(memory, model, seed=seed, kind="evaluation", condition=condition,
                     historical_context=context, artifact_id=artifact_id if condition not in {"none", "local_rule"} else "",
                     local_rule_id=local_rule_id,
                     budget=budget or Budget(), on_step=on_step, cancelled=cancelled)


def evaluate(memory, model, *, artifact_id, seeds, conditions=("none", "raw", "sleep"),
             budget=None, on_result=None, on_step=None, cancelled=None):
    import random
    seeds, conditions = list(seeds), list(conditions)
    if not seeds or len(set(seeds)) != len(seeds) or any(type(s) is not int or not 0 <= s <= 2147483647 for s in seeds):
        raise ValueError("Provide distinct nonnegative integer seeds")
    if not conditions or len(set(conditions)) != len(conditions) or not set(conditions) <= {"none", "raw", "sleep", "flat"}:
        raise ValueError("Provide distinct supported conditions")
    artifact = memory.get_artifact(artifact_id)
    experiment_id = new_id("comparison")
    directory = ROOT / "outputs" / "runs"
    directory.mkdir(parents=True, exist_ok=True)
    plan = {"id": experiment_id, "artifact_id": artifact_id, "artifact_digest": artifact["artifact_digest"],
            "model": model.name, "seeds": list(seeds), "conditions": list(conditions),
            "budget": vars(budget or Budget()), "status": "running", "results": [],
            "sleep_usage": artifact["metadata"].get("usage"),
            "limits": "Small paired smoke evaluation; preparation costs extra; no statistical or graph superiority claim."}
    path = directory / f"{experiment_id}.json"
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    pairs = [(seed, condition) for seed in seeds for condition in conditions]
    random.Random(0).shuffle(pairs)
    for seed, condition in pairs:
        if cancelled and cancelled():
            plan["status"] = "cancelled"
            break
        try:
            run = transfer(memory, model, artifact_id=artifact_id, seed=seed, condition=condition,
                           budget=budget, on_step=on_step, cancelled=cancelled)
            save_run(run)
            result = run["result"]
        except Exception as exc:
            result = {"seed": seed, "condition": condition, "success": False,
                      "termination": "infrastructure_error", "error_type": type(exc).__name__,
                      "usage_complete": False}
        plan["results"].append(result)
        path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        if on_result:
            on_result(result)
    if plan["status"] == "running":
        plan["status"] = "complete"
    plan["sleep_amortized_over_missions"] = sum(r["condition"] in {"sleep", "flat"} for r in plan["results"])
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    columns = ["seed", "condition", "success", "termination", "actions", "blocked_actions", "model_calls", "elapsed_seconds", "usage_complete"]
    with path.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(plan["results"])
    return plan
