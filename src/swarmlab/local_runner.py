"""Owns evaluator state; the local controller receives only tool-returned observations."""
from time import monotonic
from .world import World
from .local_learning import LocalController, LocalStop, extract_samples


def run_local(memory, *, mode, seed, max_actions=250, on_step=None, cancelled=lambda:False):
    frozen=memory.get_local_rule() if mode=='transfer' else None
    if mode=='transfer' and (not frozen or frozen['status']!='validated_in_scope'):
        raise ValueError('Run local learning until all cases are covered without contradictions')
    if frozen and seed in frozen.get('training_seeds', []):
        raise ValueError('Choose an unseen transfer seed; this layout already contributed learning evidence')
    episode_id=memory.create_episode(seed,'discovery' if mode=='learn' else 'evaluation',
                                     'local_training' if mode=='learn' else 'local_prepared','')
    policy=memory.register_policy('local-symbolic-v1','Finite two-switch occupancy table learned from local sensor events. BFS navigation and controlled interventions; no provider calls or private map access.')
    memory.link_policy(episode_id,policy)
    if frozen:
        memory.graph.query('MATCH (e:Episode {id:$episode}),(r:LocalRule {id:$rule}) MERGE (e)-[:USED_LOCAL_RULE]->(r)',{'episode':episode_id,'rule':frozen['id']})
    world=World.create(seed);started=monotonic();events=[]; major_count=0
    snapshots=[world.evaluator_snapshot()]
    def step(action):
        nonlocal major_count
        event=world.step(action)
        oid=memory.append_experience(episode_id,event)
        event={'id':oid,**event};events.append(event)
        snapshots.append(world.evaluator_snapshot())
        if on_step: on_step({'episode_id':episode_id,'event':event,'evaluator_snapshot':world.evaluator_snapshot()})
        samples, major = extract_samples(events)
        if len(major)>major_count:
            major_count=len(major)
            memory.ingest_local_episode(episode_id)
            memory.refresh_local_rule()
        if frozen and any(s['observation_id']==oid and frozen['table'].get(s['bits'])!=s['open'] for s in samples):
            raise LocalStop('rule_contradiction')
        return event
    controller=LocalController(step,max_actions,cancelled)
    try:
        termination=controller.learn() if mode=='learn' else controller.transfer(frozen)
    except LocalStop as exc:
        termination=str(exc)
    result={'episode_id':episode_id,'kind':'discovery' if mode=='learn' else 'evaluation',
            'condition':'local_training' if mode=='learn' else 'local_prepared','seed':seed,
            'success':world.success if mode=='transfer' else None,'termination':termination,
            'actions':world.tick,'blocked_actions':sum(e['outcome'].startswith('blocked') for e in events),
            'model_calls':0,'usage_receipts':[],'usage_complete':True,'elapsed_seconds':monotonic()-started,
            'policy_id':policy,'local_rule_id':frozen['id'] if frozen else None}
    memory.finish_episode(episode_id,result)
    learning=memory.ingest_local_episode(episode_id)
    rule=memory.refresh_local_rule()
    return {'result':result,'events':events,'local_learning':learning,'local_rule':rule,
            'evaluator_snapshots':snapshots}
