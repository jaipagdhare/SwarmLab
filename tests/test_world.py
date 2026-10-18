from collections import deque

from swarmlab.world import World, DIRECTIONS


def walk(world, robot, target):
    queue = deque([(world.robots[robot], [])])
    seen = set()
    while queue:
        pos, path = queue.popleft()
        if pos == target:
            for direction in path:
                world.step({"operation": "move", "robot_id": robot, "direction": direction})
            return
        if pos in seen:
            continue
        seen.add(pos)
        for direction, (dx, dy) in DIRECTIONS.items():
            nxt = (pos[0] + dx, pos[1] + dy)
            if nxt in world.walls or not (0 <= nxt[0] < world.width and 0 <= nxt[1] < world.height):
                continue
            if nxt == world.objects["gate_1"]["position"] and not world.gate_open:
                continue
            queue.append((nxt, path + [direction]))
    raise AssertionError("No path")


def test_layouts_are_solvable_and_gate_requires_both_holders():
    for seed in range(30):
        w = World.create(seed)
        assert not w.gate_open
        walk(w, "a", w.objects["switch_1"]["position"])
        assert not w.gate_open
        walk(w, "b", w.objects["switch_2"]["position"])
        assert w.gate_open
        walk(w, "c", w.objects["target_1"]["position"])
        assert w.success


def test_local_observations_exclude_hidden_state():
    w = World.create(11)
    obs = w.observe("a")
    assert "seed" not in obs and "success" not in obs and "walls" not in obs
    x, y = obs["position"]
    assert all(abs(o["position"][0]-x) + abs(o["position"][1]-y) <= w.visibility for o in obs["objects"])
    assert not any(o["id"] == "target_1" for o in obs["objects"])


def test_replay_and_blocked_moves():
    a, b = World.create(23), World.create(23)
    for direction in ["north"] * 10 + ["east"] * 10:
        action = {"operation": "move", "robot_id": "a", "direction": direction}
        assert a.step(action) == b.step(action)
    assert a.evaluator_snapshot() == b.evaluator_snapshot()
    assert any(e["outcome"].startswith("blocked") for e in a.history)


def test_observation_cannot_mutate_world():
    w = World.create(1)
    before = w.evaluator_snapshot()
    obs = w.observe("a")
    obs["robots"].clear()
    obs["objects"].clear()
    assert w.evaluator_snapshot() == before
