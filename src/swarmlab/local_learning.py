"""Zero-provider learning for this benchmark: observed occupancy -> observed gate state.

This is finite Boolean rule induction, not general-purpose learning or weight training.
Only step() sensor events enter the controller; private snapshots stay in the runner.
"""
from collections import deque
from itertools import product
from .world import DIRECTIONS


class Knowledge:
    def __init__(self):
        self.positions, self.cells, self.objects = {}, {}, {}
        self.events = []

    def update(self, event):
        for phase in ('before', 'after'):
            view = event[phase]
            for r in view.get('robots', []): self.positions[r['id']] = tuple(r['position'])
            self.positions[view['robot_id']] = tuple(view['position'])
            for cell in view['cells']: self.cells[tuple(cell['position'])] = cell['kind']
            for obj in view['objects']: self.objects[obj['id']] = dict(obj)
        self.events.append(event)

    def objects_of(self, kind):
        return sorted((o for o in self.objects.values() if o['kind']==kind), key=lambda o:o['id'])

    def route(self, robot, destination, allow_gate=False):
        gates={tuple(o['position']) for o in self.objects_of('gate')}
        queue=deque([(self.positions[robot],[])])
        seen={self.positions[robot]}
        while queue:
            pos, path=queue.popleft()
            if pos==tuple(destination): return path
            for direction,(dx,dy) in DIRECTIONS.items():
                nxt=(pos[0]+dx,pos[1]+dy)
                if nxt in seen or self.cells.get(nxt)!='floor' or (nxt in gates and not allow_gate): continue
                seen.add(nxt);queue.append((nxt,path+[direction]))
        return None


def extract_samples(events):
    """Known owned robot locations + a contemporaneous gate sensor reading only."""
    positions, switches, samples, major = {}, {}, [], []
    last_states={}
    for event in events:
        for phase in ('before','after'):
            view=event[phase]
            for r in view.get('robots',[]): positions[r['id']]=tuple(r['position'])
            positions[view['robot_id']]=tuple(view['position'])
            for obj in view['objects']:
                if obj['kind']=='switch': switches[obj['id']]=tuple(obj['position'])
                prop='open' if obj['kind']=='gate' else 'active' if obj['kind']=='switch' else None
                if prop:
                    key=(obj['id'],prop);value=obj[prop]
                    if key in last_states and value!=last_states[key]:
                        major.append({'observation_id':event['id'],'phase':phase,'object_id':obj['id'],
                                      'property':prop,'before':last_states[key],'after':value,
                                      'note':'Change between observations; not necessarily adjacent ticks.'})
                    last_states[key]=value
            # Explicit benchmark scope: two switch features and three owned robots.
            # Do not infer absent features or read the private simulator object list.
            if len(switches)!=2 or set(positions)!={'a','b','c'}: continue
            bits=''.join('1' if pos in positions.values() else '0' for _,pos in sorted(switches.items()))
            for obj in view['objects']:
                if obj['kind']=='gate':
                    samples.append({'id':event['id']+'_'+phase,'observation_id':event['id'],
                                    'phase':phase,'bits':bits,'open':obj['open']})
    return samples,major


def induce(samples):
    rows={''.join(bits):[] for bits in product('01',repeat=2)}
    for s in samples: rows[s['bits']].append(s)
    contradictions=[bits for bits,items in rows.items() if len({s['open'] for s in items})>1]
    missing=[bits for bits,items in rows.items() if not items]
    table={bits:items[0]['open'] for bits,items in rows.items() if items and bits not in contradictions}
    return {'status':'contradicted' if contradictions else 'validated_in_scope' if not missing else 'candidate',
            'scope':'Two observed switch occupancy bits, sorted by object ID; deterministic stationary benchmark only.',
            'table':table,'missing_cases':missing,'contradictions':contradictions,
            'evidence_ids':sorted({s['observation_id'] for s in samples}), 'model_calls':0}


class LocalStop(Exception): pass


class LocalController:
    def __init__(self, step, max_actions=250, cancelled=lambda:False):
        self.step_tool=step;self.max_actions=max_actions;self.cancelled=cancelled
        self.knowledge=Knowledge();self.actions=0

    def act(self, robot, operation='observe', direction=None):
        if self.cancelled(): raise LocalStop('cancelled')
        if self.actions>=self.max_actions: raise LocalStop('action_budget_exhausted')
        action={'robot_id':robot,'operation':operation}
        if direction: action['direction']=direction
        event=self.step_tool(action);self.actions+=1;self.knowledge.update(event)
        if event['outcome'].startswith('blocked'): raise LocalStop('unexpected_blocked_action')
        return event

    def go(self, robot, destination, allow_gate=False):
        path=self.knowledge.route(robot,destination,allow_gate)
        if path is None: raise LocalStop('no_observed_route')
        for direction in path: self.act(robot,'move',direction)

    def map_reachable(self, robot='c', allow_gate=False):
        # Frontier exploration over known floor, never private map coordinates.
        while True:
            candidates=[]
            for cell,kind in self.knowledge.cells.items():
                if kind!='floor': continue
                if not any((cell[0]+dx,cell[1]+dy) not in self.knowledge.cells for dx,dy in DIRECTIONS.values()): continue
                path=self.knowledge.route(robot,cell,allow_gate)
                if path is not None: candidates.append((len(path),cell))
            if not candidates: return
            _,destination=min(candidates)
            if destination==self.knowledge.positions[robot]:
                raise LocalStop('unresolved_frontier')
            self.go(robot,destination,allow_gate)

    def initialize(self):
        for robot in ('a','b','c'): self.act(robot)
        self.map_reachable()
        if len(self.knowledge.objects_of('switch'))!=2 or len(self.knowledge.objects_of('gate'))!=1:
            raise LocalStop('unsupported_or_incomplete_world')

    def parking(self):
        excluded={tuple(o['position']) for o in self.knowledge.objects.values()}
        cells=[p for p,k in self.knowledge.cells.items() if k=='floor' and p not in excluded
               and self.knowledge.route('c',p) is not None]
        if not cells: raise LocalStop('no_parking_cell')
        return min(cells)

    def observe_gate(self):
        gate=self.knowledge.objects_of('gate')[0]
        candidates=[(len(path),p) for p,k in self.knowledge.cells.items() if k=='floor'
                    and p not in {tuple(o['position']) for o in self.knowledge.objects_of('switch')}
                    and abs(p[0]-gate['position'][0])+abs(p[1]-gate['position'][1])<=2
                    and (path:=self.knowledge.route('c',p)) is not None]
        if not candidates: raise LocalStop('gate_not_observable')
        self.go('c',min(candidates)[1])
        event=self.act('c')
        visible=next((o for o in event['after']['objects'] if o['id']==gate['id']),None)
        if visible is None: raise LocalStop('gate_not_observable')
        return visible['open']

    def set_case(self,bits):
        park=self.parking();switches=self.knowledge.objects_of('switch')
        # C is always observer/traveler; support robots maintain the learned conditions.
        self.go('c',park)
        for robot in ('a','b'): self.go(robot,park)
        for robot,obj,bit in zip(('a','b'),switches,bits):
            if bit=='1': self.go(robot,obj['position'])
        return self.observe_gate()

    def learn(self):
        self.initialize()
        for bits in ('00','10','11','01','00'):
            self.set_case(bits)
        return 'local_experiments_complete'

    def transfer(self, rule):
        if rule['status']!='validated_in_scope': raise LocalStop('rule_not_validated')
        self.initialize()
        satisfying=sorted((b for b,v in rule['table'].items() if v),key=lambda b:(b.count('1'),b))
        if not satisfying: raise LocalStop('no_satisfying_condition')
        if not self.set_case(satisfying[0]): raise LocalStop('rule_contradiction')
        gate=self.knowledge.objects_of('gate')[0]
        self.go('c',gate['position'],allow_gate=True)
        self.map_reachable(allow_gate=True)
        targets=self.knowledge.objects_of('target')
        if not targets: raise LocalStop('target_not_observed')
        self.go('c',targets[0]['position'],allow_gate=True)
        return 'target_reached_by_observation'
