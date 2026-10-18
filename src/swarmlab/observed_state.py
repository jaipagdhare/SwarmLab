"""Navigation assistance derived exclusively from recorded local observations."""
from collections import deque
from copy import deepcopy
from .world import DIRECTIONS


def summarize(events):
    positions, cells, objects = {}, {}, {}
    tick = 0
    for event in events:
        tick = event['tick']
        for phase in ('before', 'after'):
            view = event[phase]
            for robot in view.get('robots', []):
                positions[robot['id']] = list(robot['position'])
            positions[view['robot_id']] = list(view['position'])
            for cell in view['cells']:
                cells[tuple(cell['position'])] = cell['kind']
            for obj in view['objects']:
                objects[obj['id']] = {**deepcopy(obj), 'last_seen_tick': view['tick']}
    for obj in objects.values():
        obj['robots_at_position'] = [r for r,p in positions.items() if p == list(obj['position'])]
        obj['state_may_be_stale'] = obj['last_seen_tick'] < tick
    options, routes = {}, {}
    for robot, position in positions.items():
        options[robot] = []
        for direction, (dx,dy) in DIRECTIONS.items():
            target = (position[0]+dx, position[1]+dy)
            obj = next((o for o in objects.values() if tuple(o['position']) == target and o['kind']=='gate'), None)
            status = 'unknown' if target not in cells else ('wall' if cells[target]=='wall' else 'known_floor')
            if obj:
                status = 'gate_state_stale' if obj['state_may_be_stale'] else ('gate_open' if obj.get('open') else 'gate_closed')
            options[robot].append({'direction':direction,'destination':list(target),'observed_status':status})
        routes[robot] = {}
        for oid,obj in objects.items():
            route = known_route(position, obj['position'], cells, objects)
            routes[robot][oid] = route
    return {'tick':tick,'positions':positions,'observed_objects':objects,
            'move_options':options,'routes_over_known_cells':routes,
            'recent_outcomes':[{'tick':e['tick'],'action':e['action'],'outcome':e['outcome'],
                                'actual_position':e['after']['position']} for e in events[-6:]],
            'warning':'Object state can change after its last observation. Routes are navigation suggestions, not a world solution. A null route means no known route.'}


def known_route(start, destination, cells, objects):
    start, destination = tuple(start), tuple(destination)
    queue=deque([(start,[])])
    seen={start}
    closed={tuple(o['position']) for o in objects.values() if o['kind']=='gate' and (o['state_may_be_stale'] or not o.get('open'))}
    while queue:
        pos, route = queue.popleft()
        if pos==destination: return route
        for direction,(dx,dy) in DIRECTIONS.items():
            nxt=(pos[0]+dx,pos[1]+dy)
            if nxt in seen or cells.get(nxt)!='floor' or nxt in closed: continue
            seen.add(nxt);queue.append((nxt,route+[direction]))
    return None
