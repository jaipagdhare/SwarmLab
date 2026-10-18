from swarmlab.world import World
from swarmlab.local_learning import LocalController,extract_samples,induce


def trial(seed,rule=None):
    world=World.create(seed);events=[]
    def step(action):
        event=world.step(action);event={'id':f'obs{len(events)}',**event};events.append(event);return event
    c=LocalController(step)
    result=c.transfer(rule) if rule else c.learn()
    return world,events,result


def test_learns_and_transfers_without_provider():
    world,events,_=trial(11)
    samples,major=extract_samples(events)
    rule=induce(samples)
    assert rule['status']=='validated_in_scope'
    assert rule['table']=={'00':False,'01':False,'10':False,'11':True}
    assert any(e['property']=='open' for e in major)
    for seed in [201,202,203,204,205,206,207,208,209,210]:
        w,_,_=trial(seed,rule)
        assert w.success


def test_missing_and_conflicting_evidence_cannot_validate():
    assert induce([])['status']=='candidate'
    samples=[{'bits':'00','open':False,'observation_id':'a'}, {'bits':'00','open':True,'observation_id':'b'}]
    assert induce(samples)['status']=='contradicted'


def test_does_not_assume_and_rule():
    samples=[{'bits':bits,'open':bits!='00','observation_id':bits} for bits in ['00','01','10','11']]
    assert induce(samples)['table']['10'] is True


def test_controlled_experiments_learn_or_variant_without_changing_learner():
    class OrWorld(World):
        @property
        def gate_open(self):
            return any(o['position'] in self.robots.values() for o in self.objects.values() if o['kind']=='switch')
    def execute(seed, rule=None):
        world=OrWorld.create(seed);events=[]
        def step(action):
            event={'id':f'obs{len(events)}',**world.step(action)};events.append(event);return event
        controller=LocalController(step)
        controller.transfer(rule) if rule else controller.learn()
        return world,events
    _,events=execute(11)
    rule=induce(extract_samples(events)[0])
    assert rule['table']=={'00':False,'01':True,'10':True,'11':True}
    w,_=execute(777,rule)
    assert w.success


def test_local_controller_cancels_without_calling_tool():
    import pytest
    from swarmlab.local_learning import LocalStop
    def forbidden(action): raise AssertionError('No step after cancellation')
    with pytest.raises(LocalStop,match='cancelled'):
        LocalController(forbidden,cancelled=lambda:True).learn()
