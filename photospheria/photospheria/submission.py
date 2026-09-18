"""Read and write the submission format, and check it before you upload."""
from __future__ import annotations

import json
from pathlib import Path

from .catalogue import BY_INDEX
from .engine import MAX_PER_TICK
from .level import Level


def to_submission(actions: dict[int, list]) -> dict:
    return {"actions": [
        {"tick": t,
         "plants": [{"plant_index": i, "row": r, "col": c} for i, r, c in v]}
        for t, v in sorted(actions.items()) if v]}


def from_submission(doc: dict) -> dict[int, list]:
    return {a["tick"]: [(p["plant_index"], p["row"], p["col"]) for p in a["plants"]]
            for a in doc["actions"]}


def save(actions: dict, path="out/submission.json") -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(to_submission(actions), fh)
    return path


def validate(actions: dict, level: Level) -> list[str]:
    """Everything the judge would silently ignore, reported loudly instead."""
    problems = []
    for t, plants in actions.items():
        if not isinstance(t, int) or not 0 <= t <= level.ticks - 1:
            problems.append(f"tick {t} outside 0..{level.ticks - 1}")
        if len(plants) > MAX_PER_TICK:
            problems.append(f"tick {t}: {len(plants)} plants, only the first "
                            f"{MAX_PER_TICK} will be planted")
        for idx, r, c in plants:
            if idx not in BY_INDEX:
                problems.append(f"tick {t}: plant_index {idx} is not in the catalogue")
            if not (0 <= r < level.height and 0 <= c < level.width):
                problems.append(f"tick {t}: ({r},{c}) is off the grid")
    return problems


def summarise(actions: dict) -> str:
    n = sum(len(v) for v in actions.values())
    ticks = sorted(actions)
    species = {}
    for plants in actions.values():
        for idx, _, _ in plants:
            name = BY_INDEX[idx]["plant"]
            species[name] = species.get(name, 0) + 1
    mix = ", ".join(f"{k} {v}" for k, v in sorted(species.items(), key=lambda x: -x[1]))
    return (f"{n} placements over {len(actions)} ticks "
            f"({ticks[0]}-{ticks[-1]})\n  placed: {mix}")
