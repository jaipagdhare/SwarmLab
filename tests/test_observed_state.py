from swarmlab.observed_state import summarize
from swarmlab.world import World


def test_state_uses_only_visible_data_and_routes_avoid_walls():
    world=World.create(101)
    events=[world.step({'robot_id':r,'operation':'observe'}) for r in ['a','b','c']]
    state=summarize(events)
    assert 'target_1' not in state['observed_objects']
    assert state['positions']=={r:list(p) for r,p in world.robots.items()}
    for robot,options in state['move_options'].items():
        x,y=state['positions'][robot]
        east=next(o for o in options if o['direction']=='east')
        assert east['destination']==[x+1,y]
    # Navigation cannot use a map cell never included in an observation.
    assert all('seed' not in k for k in state)


def test_closed_gate_is_not_treated_as_open_by_explanation():
    w=World.create(101)
    gate=w.objects['gate_1']['position']
    w.robots['c']=(gate[0]-1,gate[1])
    event=w.step({'robot_id':'c','operation':'move','direction':'east'})
    event['explanation']='The gate is open so cross it'
    state=summarize([event])
    assert event['outcome']=='blocked_gate'
    assert state['routes_over_known_cells']['c']['gate_1'] is None
    assert next(o for o in state['move_options']['c'] if o['direction']=='east')['observed_status']=='gate_closed'
