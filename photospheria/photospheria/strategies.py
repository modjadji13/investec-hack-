"""Planting strategies. A strategy turns a Level into {tick: [(index, row, col)]}.

The winning idea on Level 1, in two sentences:

  A cell dies 100 ticks after you plant in it, so nothing planted before tick
  400 is alive to be scored. And 99 remaining ticks x 20 placements is 1980 —
  more than the ~540 plantable cells — so you never need spreading at all. You
  hand-place the entire final grid, as late as it will fit.
"""
from __future__ import annotations

import math

from .catalogue import BY_NAME, STARTERS
from .engine import MAX_PER_TICK, CELL_NUTRIENTS, Simulator
from .level import Level


def lay_out(plan, ticks, start=None):
    """Spread a flat list of placements over consecutive ticks, 20 per tick."""
    if start is None:
        start = ticks - math.ceil(len(plan) / MAX_PER_TICK)
    actions = {}
    for i in range(0, len(plan), MAX_PER_TICK):
        t = start + i // MAX_PER_TICK
        if t >= ticks:
            break
        actions[t] = plan[i:i + MAX_PER_TICK]
    return actions


def plantable_cells(level: Level, species=STARTERS):
    """Cells at least one of `species` can occupy."""
    soils = set()
    for s in species:
        soils |= set(BY_NAME[s]["preferred_soil"])
    return [(r, c) for r in range(level.height) for c in range(level.width)
            if level.is_soil(r, c) and level.soil[r][c] in soils]


def naive_even(level: Level, species=STARTERS):
    """BASELINE, and a bad one. Scatter an even mix from tick 0 and let it grow.

    Kept because its failure is instructive: the fastest spreader takes the
    whole grid and diversity collapses. Run it to see why the rest exists.
    """
    cells = plantable_cells(level, species)
    plan = [(BY_NAME[species[i % len(species)]]["index"], r, c)
            for i, (r, c) in enumerate(sorted(cells))]
    return lay_out(plan, level.ticks, start=0)


def late_blocks(level: Level, species=STARTERS, weights=None, order=None):
    """The real strategy.

    1. Only target cells something can actually grow in.
    2. Give each species a CONTIGUOUS strip of each bed. Scattered single cells
       get overwritten the moment a neighbour matures; a block only loses its
       boundary.
    3. Place as late as the schedule fits, slowest-maturing species first, so
       almost nothing lives long enough to mature and spread.
    4. `weights` sizes the strips. Species that lose cells at the boundary get
       a bigger strip to compensate - see tune() below.
    """
    cells = plantable_cells(level, species)
    weights = list(weights or [1.0] * len(species))
    w = [max(0.02, x) for x in weights]
    total = sum(w)
    fracs = [x / total for x in w]

    by_species = {s: [] for s in species}
    for bed in level.beds(cells):
        rows = [r for r, _ in bed]
        cols = [c for _, c in bed]
        vertical = (max(rows) - min(rows)) >= (max(cols) - min(cols))
        ordered = sorted(bed, key=lambda rc: rc if vertical else (rc[1], rc[0]))
        edges, acc = [], 0.0
        for f in fracs:
            acc += f
            edges.append(acc * len(ordered))
        for i, (r, c) in enumerate(ordered):
            k = 0
            while k < len(species) - 1 and i >= edges[k]:
                k += 1
            by_species[species[k]].append((r, c))

    if order is None:
        order = sorted(species, key=lambda s: -BY_NAME[s]["growth"]["time_to_maturity"])

    plan = []
    for s in order:
        idx = BY_NAME[s]["index"]
        plan += [(idx, r, c) for r, c in by_species[s]]
    return lay_out(plan, level.ticks)


def tune(level: Level, species=STARTERS, order=None, rounds=9, verbose=True):
    """Feedback loop: run, see which species lost cells, widen their strips.

    This is the whole optimisation. No search, no annealing - just measure the
    error and push against it. Returns (best_actions, best_score, weights).
    """
    target = len(plantable_cells(level, species)) / len(species)
    weights = [1.0] * len(species)
    best = None
    for i in range(rounds):
        actions = late_blocks(level, species, weights, order)
        sim = Simulator(level_copy(level)).run(actions)
        s = sim.score()
        if verbose:
            got = " ".join(f"{sp.split()[0][:4]}:{s['counts'].get(sp, 0)}" for sp in species)
            print(f"  round {i}  H={s['H']:.4f}  final={s['final']:.4f}   {got}")
        if best is None or s["final"] > best[1]["final"]:
            best = (actions, s, list(weights))
        for j, sp in enumerate(species):
            got = max(s["counts"].get(sp, 0), 1)
            weights[j] *= (target / got) ** 0.45
    return best


def level_copy(level: Level) -> Level:
    """A fresh Level - the engine mutates soil (burnt_soil_radius), so reuse is unsafe."""
    return Level(width=level.width, height=level.height, ticks=level.ticks,
                 soil=[row[:] for row in level.soil],
                 terrain=[row[:] for row in level.terrain],
                 events=dict(level.events), seasons=dict(level.seasons),
                 animals_enabled=level.animals_enabled, defined=list(level.defined))


def safe_planting_tick(level: Level) -> int:
    """Earliest tick whose plants are still alive on the final tick."""
    return level.ticks - int(CELL_NUTRIENTS) + 1


STRATEGIES = {"naive": naive_even, "blocks": late_blocks}
