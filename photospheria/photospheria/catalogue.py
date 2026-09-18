"""Loads the four data files and evaluates the two kinds of condition tree.

The challenge ships two tree formats for the same idea, which is a wart you just
have to live with:

    plant unlocks   {"op": "AND", "children": [...]}    leaves: type/plant/operator/value
    animal triggers {"type": "AND", "conditions": [...]} leaves: type/species/threshold/operator
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(name: str):
    with open(DATA_DIR / name) as fh:
        return json.load(fh)


PLANTS = _load("plant_dataset.json")
UNLOCKS = _load("plant_unlock_conditions.json")
ANIMALS = _load("animals.json")
CLASSES = _load("classifications.json")

BY_NAME = {p["plant"]: p for p in PLANTS}
BY_INDEX = {p["index"]: p for p in PLANTS}
UNLOCK_BY_NAME = {u["plant"]: u["unlock"] for u in UNLOCKS}
ANIMAL_BY_NAME = {a["name"]: a for a in ANIMALS}

N_SPECIES = len(PLANTS)            # 31 - the base of the entropy logarithm
STARTERS = ["Grass", "Rose Bush", "Lavender", "Dwarf Sunflower", "Oak Tree"]

DIRT, MUD, CLAY, BURNT = 0, 1, 2, 3

OPS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "=": lambda a, b: a == b,
}


def _norm(s: str) -> str:
    return s.lower().replace("-", "").replace(" ", "")


# DATA QUIRK: animals.json asks for the group "Shallow-root Species"; the key in
# classifications.json is "Shallowroot Species". Matched literally, Rhizorends
# never appears and Bloodbloom is unreachable. We match on a normalised name.
CLASSES_NORM = {_norm(k): v for k, v in CLASSES.items()}


def group_members(names) -> list[str]:
    """A species_group entry is either a classification name or a plain species."""
    out: list[str] = []
    for n in names:
        out.extend(CLASSES_NORM.get(_norm(n), [n]))
    return out


def classes_of(species: str) -> list[str]:
    return [k for k, v in CLASSES.items() if species in v]


class WorldView:
    """The snapshot a condition tree is evaluated against."""

    def __init__(self, counts, cells_total, animals, events_fired, features, dominance):
        self.counts = counts
        self.cells_total = cells_total
        self.animals = animals
        self.events = events_fired
        self.features = features
        self.dominance = dominance

    def cov(self, plant):
        return self.counts.get(plant, 0) / self.cells_total

    def group_cov(self, names):
        return sum(self.counts.get(s, 0) for s in group_members(names)) / self.cells_total

    def group_count(self, names):
        return sum(self.counts.get(s, 0) for s in group_members(names))


def eval_unlock(node, w: WorldView) -> bool:
    op = node.get("op")
    if op == "AND":
        return all(eval_unlock(c, w) for c in node["children"])
    if op == "OR":
        return any(eval_unlock(c, w) for c in node["children"])
    if op == "NOT":
        return not eval_unlock(node["child"], w)

    t = node["type"]
    if t == "species_present":
        s = node["species"]
        return s in w.animals or w.counts.get(s, 0) > 0
    if t == "species_absent":
        s = node["species"]
        return not (s in w.animals or w.counts.get(s, 0) > 0)
    if t == "coverage":
        return OPS[node["operator"]](w.cov(node["plant"]), node["value"])
    if t == "count":
        return OPS[node["operator"]](w.counts.get(node["plant"], 0), node["value"])
    if t == "event":
        return node["event"] in w.events
    if t == "feature_count":
        v = w.features.get(node["feature"], 0)
        # dead_matter thresholds are fractions (0.05); burnt_soil is a count (20)
        if node["value"] < 1:
            v = v / w.cells_total
        return OPS[node["operator"]](v, node["value"])
    raise ValueError(f"unknown unlock leaf type: {t}")


def eval_animal(node, w: WorldView) -> bool:
    t = node.get("type")
    if t == "AND":
        return all(eval_animal(c, w) for c in node["conditions"])
    if t == "OR":
        return any(eval_animal(c, w) for c in node["conditions"])

    opf = OPS[node.get("operator", ">=")]
    if t == "coverage":
        return opf(w.group_cov(node["species"]), node["threshold"])
    if t == "group_coverage":
        return opf(w.group_cov(node["species_group"]), node["threshold"])
    if t == "count":
        if "species_group" in node:
            n = w.group_count(node["species_group"])
        else:
            n = w.counts.get(node["species"], 0)
        return opf(n, node["threshold"])
    if t == "dominance":
        return w.dominance >= node["threshold"]
    raise ValueError(f"unknown animal condition type: {t}")


def present_animals(w: WorldView) -> set[str]:
    """Animals are re-derived every tick - they leave when conditions lapse."""
    out: set[str] = set()
    for _ in range(3):                      # small fixed point
        changed = False
        for a in ANIMALS:
            w.animals = out
            if a["name"] not in out and eval_animal(a["requirements"], w):
                out = out | {a["name"]}
                changed = True
        if not changed:
            break
    w.animals = out
    return out


def unlocked_plants(w: WorldView) -> set[str]:
    out = set(STARTERS)
    for p in PLANTS:
        name = p["plant"]
        if name in out:
            continue
        tree = UNLOCK_BY_NAME.get(name)
        if tree is None or eval_unlock(tree, w):
            out.add(name)
    return out
