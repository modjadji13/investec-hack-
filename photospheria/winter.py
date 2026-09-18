"""Winter-window plan for the 800-tick levels, built from what the judge logs said.

What the logs established (see calibrate.py):
  * Rose Bush and Lavender cannot spread in Winter, and ticks 701-799 ARE Winter
    on Levels 3 and 4. They are dead weight there.
  * Crimson Vine never unlocked in any judge run. Every placement of it was
    refused: 472 on Level 3, 513 on Level 4. Don't bet on it.
  * Razorgrass and Crystal Cactus DO unlock inside the window once Grass covers
    4-5% of the grid - both ended in the thousands on Levels 3 and 4.
  * Oak spreads far more than the PDF suggests: 104 seeds became 26,985 cells on
    Level 4 (54% of everything alive). It is the fill engine, and the thing to
    keep on a leash.
  * Placing onto a cell held by a DIFFERENT species is allowed; the same species
    is refused. So late placements can take cells back from Oak.

The plan, adaptive against the calibrated engine:
  1. Grass first - it is the key that unlocks the other two.
  2. Oak and Sunflower seeds, Oak on a wide lattice in a narrow strip.
  3. Razorgrass and Crystal Cactus the moment the engine unlocks them.
  4. Final stretch: fill gaps, then reclaim Oak cells for whoever is short.
"""
from __future__ import annotations

from collections import defaultdict

from .catalogue import BY_NAME
from .engine import MAX_PER_TICK, Simulator
from .strategies import level_copy, plantable_cells

SPECIES = ["Oak Tree", "Razorgrass", "Crystal Cactus", "Grass", "Dwarf Sunflower"]


def _strips(level, species, weights, cells):
    cols = sorted({c for _, c in cells})
    lo, hi = min(cols), max(cols)
    w = [max(0.02, x) for x in weights]
    tot = sum(w)
    edges, acc = [], 0.0
    for x in w:
        acc += x / tot
        edges.append(lo + acc * (hi - lo + 1))
    owner = {}
    for (r, c) in cells:
        k = 0
        while k < len(species) - 1 and c >= edges[k]:
            k += 1
        owner[(r, c)] = species[k]
    return owner


def solve(level, weights=(0.35, 1, 1, 1, 1), strides=None, start=None,
          topup_from=None, delays=None, verbose=True):
    """`delays` = ticks after `start` before a species is seeded. High-rank
    spreaders (Oak 10, Razorgrass 8) win every boundary, so they get less time."""
    delays = delays or {"Oak Tree": 30, "Razorgrass": 35}
    species = SPECIES
    strides = strides or {"Oak Tree": 14, "Razorgrass": 7, "Crystal Cactus": 7,
                          "Grass": 6, "Dwarf Sunflower": 6}
    start = start or level.ticks - 99
    topup_from = topup_from or level.ticks - 40

    cells = sorted(plantable_cells(level, species))
    owner = _strips(level, species, weights, cells)
    lattice = {sp: [(r, c) for (r, c) in cells
                    if owner[(r, c)] == sp and r % strides[sp] == 0 and c % strides[sp] == 0]
               for sp in species}
    # Grass also gets a thin sprinkle everywhere: coverage is a global percentage
    # and the unlocks need it fast, wherever it comes from.
    grass_sprinkle = [(r, c) for (r, c) in cells if r % 25 == 12 and c % 25 == 12]
    queue = {sp: list(lattice[sp]) for sp in species}
    queue["Grass"] = grass_sprinkle + queue["Grass"]
    cursor = defaultdict(int)

    sim = Simulator(level_copy(level))
    actions = {}
    # seeding priority by tick offset: Grass first, then Oak/Sunflower, then the unlockables
    order_for = lambda t: (["Grass"] if t < start + 3 else
                           ["Oak Tree", "Dwarf Sunflower", "Grass"] if t < start + 20 else
                           ["Razorgrass", "Crystal Cactus", "Oak Tree", "Dwarf Sunflower", "Grass"])

    for t in range(level.ticks):
        acts = []
        if t >= start:
            for sp in order_for(t):
                if sp not in sim.unlocked or t < start + delays.get(sp, 0):
                    continue
                q = queue[sp]
                while cursor[sp] < len(q) and len(acts) < MAX_PER_TICK:
                    r, c = q[cursor[sp]]
                    cursor[sp] += 1
                    if sim.g[r][c].species != sp and sim.can_occupy(sp, r, c):
                        acts.append((BY_NAME[sp]["index"], r, c))
                if len(acts) >= MAX_PER_TICK:
                    break
            if t >= topup_from and len(acts) < MAX_PER_TICK:
                counts = sim.counts()
                pool = [s for s in species if s in sim.unlocked]
                target = (sum(counts.values()) or 1) / len(pool)
                fattest = max(pool, key=lambda s: counts.get(s, 0))
                taken = {(r, c) for _, r, c in acts}
                for want_empty in (True, False):
                    for sp in sorted(pool, key=lambda s: counts.get(s, 0)):
                        if len(acts) >= MAX_PER_TICK or counts.get(sp, 0) >= target:
                            continue
                        for (r, c) in cells:
                            if len(acts) >= MAX_PER_TICK:
                                break
                            occ = sim.g[r][c].species
                            ok = (occ is None) if want_empty else (occ == fattest and occ != sp)
                            if ok and (r, c) not in taken and sim.can_occupy(sp, r, c):
                                acts.append((BY_NAME[sp]["index"], r, c))
                                taken.add((r, c))
                    if len(acts) >= MAX_PER_TICK:
                        break
        acts = acts[:MAX_PER_TICK]
        if acts:
            actions[t] = acts
        sim.step(acts)
        if verbose and t >= start and (t - start) % 25 == 0:
            s = sim.score()
            print(f"  t{t}  unlocked {sorted(x.split()[0] for x in sim.unlocked)}  "
                  f"C {s['C']}  H {s['H']:.3f}  rej {sim.rejected}")
    return actions, sim
