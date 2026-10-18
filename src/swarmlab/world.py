"""Deterministic world. Only observe()/step() results belong in model context."""
from copy import deepcopy
from dataclasses import dataclass, field
import random

DIRECTIONS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
ROBOTS = ("a", "b", "c")


@dataclass
class World:
    seed: int
    width: int = 9
    height: int = 7
    tick: int = 0
    visibility: int = 2
    traveler: str = "c"
    robots: dict = field(default_factory=dict)
    objects: dict = field(default_factory=dict)
    walls: set = field(default_factory=set)
    history: list = field(default_factory=list)

    @classmethod
    def create(cls, seed: int, traveler: str = "c"):
        if traveler not in ROBOTS:
            raise ValueError("Unknown traveler")
        rng = random.Random(seed)
        gate_y = rng.randint(1, 5)
        cells = [(x, y) for x in range(1, 4) for y in range(1, 6)]
        starts = rng.sample(cells, 3)
        switches = rng.sample([p for p in cells if p not in starts], 2)
        world = cls(seed=seed, traveler=traveler)
        world.robots = dict(zip(ROBOTS, starts))
        world.objects = {
            "switch_1": {"kind": "switch", "position": switches[0]},
            "switch_2": {"kind": "switch", "position": switches[1]},
            "gate_1": {"kind": "gate", "position": (4, gate_y)},
            "target_1": {"kind": "target", "position": (7, gate_y)},
        }
        world.walls = {(x, y) for x in range(world.width) for y in range(world.height)
                       if x in (0, world.width - 1) or y in (0, world.height - 1) or (x == 4 and y != gate_y)}
        return world

    @property
    def gate_open(self):
        occupied = set(self.robots.values())
        return all(obj["position"] in occupied for obj in self.objects.values() if obj["kind"] == "switch")

    @property
    def success(self):
        return self.robots[self.traveler] == self.objects["target_1"]["position"]

    def observe(self, robot_id: str):
        if robot_id not in self.robots:
            raise ValueError("Unknown robot")
        x, y = self.robots[robot_id]
        visible = {(cx, cy) for cx in range(self.width) for cy in range(self.height)
                   if abs(cx - x) + abs(cy - y) <= self.visibility}
        objects = []
        for object_id, obj in self.objects.items():
            if obj["position"] not in visible:
                continue
            item = {"id": object_id, **deepcopy(obj)}
            if obj["kind"] == "switch":
                item["active"] = obj["position"] in self.robots.values()
            if obj["kind"] == "gate":
                item["open"] = self.gate_open
            objects.append(item)
        return {
            "tick": self.tick, "robot_id": robot_id, "position": (x, y),
            "cells": [{"position": p, "kind": "wall" if p in self.walls else "floor"} for p in sorted(visible)],
            "objects": objects,
            "robots": [{"id": r, "position": p} for r, p in self.robots.items() if p in visible],
        }

    def step(self, action: dict):
        robot_id = action.get("robot_id")
        if robot_id not in ROBOTS:
            raise ValueError("Unknown robot")
        operation = action.get("operation")
        if operation not in {"move", "observe", "wait"}:
            raise ValueError("Unknown operation")
        before = self.observe(robot_id)
        outcome = "observed" if operation == "observe" else "waited"
        if operation == "move":
            direction = action.get("direction")
            if direction not in DIRECTIONS:
                raise ValueError("Unknown direction")
            dx, dy = DIRECTIONS[direction]
            x, y = self.robots[robot_id]
            target = (x + dx, y + dy)
            if target in self.walls or not (0 <= target[0] < self.width and 0 <= target[1] < self.height):
                outcome = "blocked_wall"
            elif target == self.objects["gate_1"]["position"] and not self.gate_open:
                outcome = "blocked_gate"
            else:
                # Robot bodies can share cells; this is explicit tool semantics.
                self.robots[robot_id] = target
                outcome = "moved"
        self.tick += 1
        event = {"action": deepcopy(action), "before": before,
                 "outcome": outcome, "after": self.observe(robot_id), "tick": self.tick}
        self.history.append(deepcopy(event))
        return event

    def evaluator_snapshot(self):
        """Private full state for scoring/rendering, never for the model."""
        return {"seed": self.seed, "tick": self.tick, "width": self.width, "height": self.height,
                "robots": deepcopy(self.robots), "objects": deepcopy(self.objects),
                "walls": sorted(self.walls), "gate_open": self.gate_open,
                "success": self.success, "traveler": self.traveler}
