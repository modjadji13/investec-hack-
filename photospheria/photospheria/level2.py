"""Level 2 strategy — Garden Growth Study. 100x70, 500 ticks, animals ON.

Why Level 2 needs a different plan from Level 1
-----------------------------------------------
Level 1:  1980 placements for   540 cells  -> hand-place the entire final grid.
Level 2:  1980 placements for  6712 cells  -> you can place only 30% of it.
          Spreading stops being a nuisance and becomes the mechanism.

And the prize is much bigger. With animals enabled and a Rain event at tick 250,
29 of 31 species are reachable (Crystal Cactus needs Drought and Phoenix Bloom
needs Ash Eclipse; neither fires here). That lifts the diversity ceiling from
Level 1's 0.4687 to 0.9806.

    ceiling with all 29 species  =  0.8 x 0.9806 x (6712/7000)  =  0.75
    ceiling with only the 5 starters                            =  0.36

So unlocking the tree is worth roughly DOUBLE everything else on this level.

What works, and why
-------------------
1. TERRITORY, not interleaving. Seeding a mixed lattice fails completely: the
   fastest spreader takes every cell and diversity goes to zero (measured: fill
   95.9%, H 0.0000). Giving each species a contiguous vertical strip means only
   the strip boundaries are contested. Same seeds, H 0.39 instead of 0.00.

2. SEED SPARSELY, let it spread. A stride-5 lattice is 270 seeds; they fill
   95.9% of the grid on their own by tick ~470. Denser seeding is wasted budget.

3. SPEND THE REST ON A LATE REBALANCE. Seeding uses 270 of 1980 placements. The
   rest goes into the final ticks, topping up whichever species is behind. A
   plant placed at tick 490 has almost no time to be overwritten.

Known weakness: Rose Bush still ends up thin. It spreads Row/range-1 at rate 2
and loses every boundary it has. It needs its own isolated block rather than
top-ups scattered into rival territory.
"""
from __future__ import annotations

from .catalogue import BY_NAME, STARTERS
from .engine import MAX_PER_TICK, Simulator
from .strategies import level_copy, plantable_cells

SEED_STRIDE = 5          # 1 seed per 5x5 block - enough to fill by tick 470
SEED_START = 401         # earliest tick whose plants survive to 500
TOPUP_FROM = 440


def territory_seeds(level, species, stride=SEED_STRIDE, start=SEED_START,
                    weights=None):
    """One contiguous vertical strip per species, seeded on a lattice."""
    cells = sorted(plantable_cells(level, list(BY_NAME)))
    cols = sorted({c for _, c in cells})
    lo, hi = min(cols), max(cols)
    n = len(species)
    w = [max(0.02, x) for x in (weights or [1.0] * n)]
    total = sum(w)
    edges, acc = [], 0.0
    for x in w:
        acc += x / total
        edges.append(lo + acc * (hi - lo + 1))

    def strip_of(c):
        k = 0
        while k < n - 1 and c >= edges[k]:
            k += 1
        return k

    plan = [(BY_NAME[species[strip_of(c)]]["index"], r, c)
            for (r, c) in cells if not (r % stride or c % stride)]
    return ({start + i // MAX_PER_TICK: plan[i:i + MAX_PER_TICK]
             for i in range(0, len(plan), MAX_PER_TICK)}, cells)


def solve(level, species=STARTERS, stride=SEED_STRIDE, start=SEED_START,
          topup_from=TOPUP_FROM, weights=None, verbose=True):
    seeds, cells = territory_seeds(level, species, stride, start, weights)
    sim = Simulator(level_copy(level))
    actions = {}

    for t in range(level.ticks):
        acts = list(seeds.get(t, []))
        if t >= topup_from and len(acts) < MAX_PER_TICK:
            counts = sim.counts()
            filled = sum(counts.values()) or 1
            target = filled / len(species)
            fattest = max(species, key=lambda s: counts.get(s, 0))
            # EMPTY CELLS FIRST. Overwriting the fattest species only moves a
            # cell from one column to another; filling a gap raises BOTH the
            # short species' count and the fill factor, which is the term with
            # the exponent on it. Only once the gaps are gone is it worth
            # taking cells off the leader.
            for want_empty in (True, False):
                for sp in sorted(species, key=lambda s: counts.get(s, 0)):
                    if len(acts) >= MAX_PER_TICK or counts.get(sp, 0) >= target:
                        continue
                    for (r, c) in cells:
                        if len(acts) >= MAX_PER_TICK:
                            break
                        occupant = sim.g[r][c].species
                        ok = (occupant is None) if want_empty else (occupant == fattest)
                        if ok and sim.can_occupy(sp, r, c):
                            acts.append((BY_NAME[sp]["index"], r, c))
                if len(acts) >= MAX_PER_TICK:
                    break
        acts = acts[:MAX_PER_TICK]
        if acts:
            actions[t] = acts
        sim.step(acts)
        if verbose and t and t % 100 == 0:
            s = sim.score()
            print(f"  t{t:>3}  species {s['species']:>2}  filled {s['C']:>4}  "
                  f"H {s['H']:.3f}")

    return actions, sim


# ---------------------------------------------------------------------------
# Tech phase: unlock species before seeding, then seed EVERYTHING unlocked.
# Seeding only the 5 starters when 10 species are available throws away a third
# of the achievable diversity.
# ---------------------------------------------------------------------------
from collections import defaultdict                                    # noqa: E402
from .catalogue import (ANIMALS, UNLOCK_BY_NAME, ANIMAL_BY_NAME,       # noqa: E402
                        group_members)


def _plant_demand(node, w, out):
    if "op" in node:
        if node["op"] == "AND":
            for c in node["children"]:
                _plant_demand(c, w, out)
        elif node["op"] == "OR":
            best, cost = None, None
            for c in node["children"]:
                probe = defaultdict(float)
                _plant_demand(c, w, probe)
                s = sum(probe.values())
                if cost is None or s < cost:
                    best, cost = c, s
            if best is not None:
                _plant_demand(best, w, out)
        return
    t = node["type"]
    if t == "coverage":
        need = node["value"] * w.cells_total - w.counts.get(node["plant"], 0)
        if need > 0:
            out[node["plant"]] += need
    elif t == "count":
        need = node["value"] - w.counts.get(node["plant"], 0)
        if need > 0:
            out[node["plant"]] += need


def _animal_demand(node, w, out):
    t = node.get("type")
    if t in ("AND", "OR"):
        for c in node["conditions"]:
            _animal_demand(c, w, out)
        return
    names = node.get("species") or node.get("species_group") or []
    if isinstance(names, str):
        names = [names]
    members = group_members(names)
    if not members:
        return
    have = sum(w.counts.get(m, 0) for m in members)
    if t in ("coverage", "group_coverage"):
        need = node["threshold"] * w.cells_total - have
    elif t == "count":
        need = node["threshold"] - have
    else:
        return
    if need > 0:
        for m in members:
            out[m] += 1.5 * need / len(members)


def tech_step(sim, cells, cursor):
    """Plant whatever most reduces the unmet conditions of what is still locked."""
    w = sim.world()
    demand = defaultdict(float)
    for name, tree in UNLOCK_BY_NAME.items():
        if name not in sim.unlocked:
            _plant_demand(tree, w, demand)
    for a in ANIMALS:
        if a["name"] not in sim.animals:
            _animal_demand(a["requirements"], w, demand)

    # Cap the runaway spreaders. Grass is needed at 4-5% coverage to summon
    # Loamcrawlers, Verdelopes and Grazeleths - and for nothing else. Left
    # uncapped it floods the map, drains every cell's nutrients, and there is
    # nothing left alive by the time the scoring window opens.
    counts = sim.counts()
    caps = {"Grass": 0.06, "Razorgrass": 0.04, "Dwarf Sunflower": 0.05}
    ranked = sorted(((v, k) for k, v in demand.items()
                     if k in sim.unlocked and k in BY_NAME
                     and counts.get(k, 0) < caps.get(k, 1.0) * w.cells_total),
                    reverse=True)
    acts = []
    for _, sp in ranked:
        if len(acts) >= MAX_PER_TICK:
            break
        want, i, tries = min(MAX_PER_TICK - len(acts), 10), cursor[sp], 0
        placed = 0
        while placed < want and tries < len(cells):
            r, c = cells[(i + tries) % len(cells)]
            tries += 1
            if sim.g[r][c].species != sp and sim.can_occupy(sp, r, c):
                acts.append((BY_NAME[sp]["index"], r, c))
                placed += 1
        cursor[sp] = (i + tries) % max(len(cells), 1)
    return acts[:MAX_PER_TICK]


def solve_with_tech(level, tech_until=200, tech_rows=0.22, seed_start=SEED_START,
                    stride=SEED_STRIDE, topup_from=TOPUP_FROM, verbose=True):
    """Tech phase -> fallow (let nutrients regenerate) -> seed every species
    that got unlocked -> late rebalance."""
    cells = sorted(plantable_cells(level, list(BY_NAME)))
    # The tech phase is confined to a nursery. Everywhere it touches loses
    # nutrients, and a cell only supports 100 ticks of growth EVER - so the
    # rest of the map has to stay untouched until the scoring window.
    cut = int(level.height * tech_rows)
    nursery = [(r, c) for r, c in cells if r < cut]
    sim = Simulator(level_copy(level))
    actions, cursor = {}, defaultdict(int)
    seeds = None

    for t in range(level.ticks):
        if t < tech_until:
            acts = tech_step(sim, nursery, cursor)
        elif t < seed_start:
            acts = []                                     # fallow: regenerate
        else:
            if seeds is None:
                species = sorted(sim.unlocked)
                if verbose:
                    print(f"  seeding {len(species)} species: "
                          f"{', '.join(s.split()[0] for s in species)}")
                seeds, _ = territory_seeds(level, species, stride, seed_start)
                seeds = [p for tt in sorted(seeds) for p in seeds[tt]]
            take, seeds = seeds[:MAX_PER_TICK], seeds[MAX_PER_TICK:]
            acts = list(take)
            if t >= topup_from and len(acts) < MAX_PER_TICK:
                counts = sim.counts()
                pool = sorted(sim.unlocked)
                filled = sum(counts.values()) or 1
                target = filled / len(pool)
                fattest = max(pool, key=lambda s: counts.get(s, 0))
                for sp in sorted(pool, key=lambda s: counts.get(s, 0)):
                    if len(acts) >= MAX_PER_TICK or counts.get(sp, 0) >= target:
                        continue
                    for (r, c) in cells:
                        if len(acts) >= MAX_PER_TICK:
                            break
                        if sim.g[r][c].species == fattest and sim.can_occupy(sp, r, c):
                            acts.append((BY_NAME[sp]["index"], r, c))
        acts = acts[:MAX_PER_TICK]
        if acts:
            actions[t] = acts
        sim.step(acts)
        if verbose and t and t % 100 == 0:
            s = sim.score()
            print(f"  t{t:>3} unlocked {len(sim.unlocked):>2} animals "
                  f"{len(sim.animals)} species {s['species']:>2} H {s['H']:.3f}")
    return actions, sim
