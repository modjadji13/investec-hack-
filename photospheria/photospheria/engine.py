"""The simulation engine — a REPLICA of the hidden judge, not the judge itself.

Every place the problem statement is ambiguous is marked `ASSUMPTION`. Those are
the knobs to re-tune when a local score disagrees with the leaderboard. Each one
is a one-line change; none of them is buried in logic.

  A1  CrossHatch spreads on the diagonals (the "X" to Moore's box).
  A2  Spread resolves in row-major order. "Last writer wins" means this matters
      and the real engine's order is undocumented.
  A3  Coverage is denominated by the WHOLE grid (width x height), not by the
      habitable cells only. The spec says Cmax = N x M.
  A4  Unlocks are recalculated each tick; species can lock again when a
      required animal, event, or coverage condition lapses. Confirmed by the
      official evaluation logs.
  A5  A plant standing on dead matter drains 0.5/tick instead of 1.0/tick
      (the literal reading of the spec).
  A6  Manual plantings resolve before spreading within a tick.
"""
from __future__ import annotations

import math
from collections import defaultdict

from .catalogue import (BURNT, BY_INDEX, BY_NAME, N_SPECIES, STARTERS,
                        WorldView, classes_of, group_members,
                        present_animals, unlocked_plants, ANIMALS)
from .level import Level

MAX_PER_TICK = 20
CELL_NUTRIENTS = 100.0


def pattern_offsets(spread_type: str, rng: int) -> list[tuple[int, int]]:
    o: list[tuple[int, int]] = []
    if spread_type == "VonNeumann":
        for d in range(1, rng + 1):
            o += [(-d, 0), (d, 0), (0, -d), (0, d)]
    elif spread_type == "Moore":
        for dr in range(-rng, rng + 1):
            for dc in range(-rng, rng + 1):
                if (dr, dc) != (0, 0):
                    o.append((dr, dc))
    elif spread_type == "Row":
        for d in range(1, rng + 1):
            o += [(0, -d), (0, d)]
    elif spread_type == "Column":
        for d in range(1, rng + 1):
            o += [(-d, 0), (d, 0)]
    elif spread_type == "CrossHatch":                       # ASSUMPTION A1
        for d in range(1, rng + 1):
            o += [(-d, -d), (-d, d), (d, -d), (d, d)]
    else:
        raise ValueError(f"unknown spread_type: {spread_type}")
    return o


class Cell:
    __slots__ = ("species", "planted_tick", "age", "mature", "nutrients",
                 "dead_matter", "sub")

    def __init__(self):
        self.species = None
        self.planted_tick = -1
        self.age = 0
        self.mature = False
        self.nutrients = CELL_NUTRIENTS
        self.dead_matter = False
        self.sub = None          # subsurface_growth occupant (Whiteveil Mycelium)


class Simulator:
    def __init__(self, level: Level):
        self.L = level
        self.g = [[Cell() for _ in range(level.width)] for _ in range(level.height)]
        self.tick = 0
        self.events_fired: set[str] = set()
        self.season = level.seasons.get(0, "Spring")
        self.animals: set[str] = set()
        self.unlocked: set[str] = set(STARTERS)
        self.shade = [[0] * level.width for _ in range(level.height)]
        self.log: list[tuple] = []
        self.rejected = 0            # placements the engine ignored

    # ---------- helpers ----------
    def inb(self, r, c) -> bool:
        return 0 <= r < self.L.height and 0 <= c < self.L.width

    def counts(self) -> dict[str, int]:
        d: dict[str, int] = defaultdict(int)
        for row in self.g:
            for cell in row:
                if cell.species:
                    d[cell.species] += 1
        return dict(d)

    def rules_of(self, species):
        r = BY_NAME[species]["rules"]
        return ({w["type"]: w for w in r["weaknesses"]},
                {s["type"]: s for s in r["special"]})

    def neighbours(self, r, c) -> int:
        n = 0
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            if self.inb(r + dr, c + dc) and self.g[r + dr][c + dc].species:
                n += 1
        return n

    def world(self) -> WorldView:
        c = self.counts()
        pop = sum(c.values())
        feats = {
            "dead_matter": sum(1 for row in self.g for x in row if x.dead_matter),
            "burnt_soil": sum(1 for r in range(self.L.height)
                              for cc in range(self.L.width)
                              if self.L.soil[r][cc] == BURNT),
        }
        dom = max(c.values()) / pop if pop else 0.0
        return WorldView(c, self.L.cells_total, set(self.animals),   # ASSUMPTION A3
                         self.events_fired, feats, dom)

    def animal_mods(self, species) -> tuple[float, float, float]:
        """(spread_rate multiplier, maturation multiplier, spread_range multiplier)"""
        sr = mat = rng = 1.0
        cls = set(classes_of(species)) | {species}
        for a in ANIMALS:
            if a["name"] not in self.animals:
                continue
            for e in a["effects"]:
                tgt = set(group_members([e["target"]])) | {e["target"]}
                if not (cls & tgt):
                    continue
                if e["type"] == "spread_rate":
                    sr *= e["value"]
                elif e["type"] == "maturation_rate":
                    mat *= e["value"]
                elif e["type"] in ("spread_range", "seed_dispersal"):
                    rng *= e["value"]
        return sr, mat, rng

    def growth_of(self, species) -> dict:
        g = dict(BY_NAME[species]["growth"])
        for m in g.get("conditional_modifiers") or []:
            if m["condition"] == f"season_{self.season.lower()}":
                g.update({k: v for k, v in m.items() if k != "condition"})
        return g

    # ---------- placement ----------
    def can_occupy(self, species, r, c) -> bool:
        if not self.inb(r, c):
            return False
        weak, spec = self.rules_of(species)
        if self.L.terrain[r][c] != "soil":
            if not (self.L.terrain[r][c] == "crack" and "crack_spread" in spec):
                return False
        if self.L.soil[r][c] not in BY_NAME[species]["preferred_soil"]:
            return False
        if self.g[r][c].nutrients <= 0:
            return False
        if "no_shade_survival" in weak and self.shade[r][c] and "can_grow_in_shade" not in spec:
            return False
        if "shade_required" in weak and not self.shade[r][c]:
            return False
        if "must_be_burnt_soil" in weak and self.L.soil[r][c] != BURNT:
            return False
        if "must_be_adjacent_to" in weak:
            feat = weak["must_be_adjacent_to"]["feature"]
            want = {"water": {"water"}, "rock_or_path": {"stone", "path"}}.get(feat, {feat})
            if not any(self.inb(r + dr, c + dc) and self.L.terrain[r + dr][c + dc] in want
                       for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                return False
        if "no_adjacent_plants" in weak and self.neighbours(r, c) > 0:
            return False
        return True

    def place(self, species, r, c) -> bool:
        if not self.can_occupy(species, r, c):
            return False
        cell = self.g[r][c]
        _, spec = self.rules_of(species)
        if cell.species and cell.species != species and "subsurface_growth" in spec:
            cell.sub = species                      # grows underneath instead
            return True
        cell.species = species
        cell.planted_tick = self.tick
        cell.age = 0
        cell.mature = False
        cell.dead_matter = False
        return True

    def kill(self, r, c):
        cell = self.g[r][c]
        if cell.sub:                                # subsurface promotion
            cell.species, cell.sub = cell.sub, None
            cell.age, cell.mature, cell.planted_tick = 0, False, self.tick
            return
        cell.species = None
        cell.age = 0
        cell.mature = False
        cell.dead_matter = True

    def recompute_shade(self):
        self.shade = [[0] * self.L.width for _ in range(self.L.height)]
        for r in range(self.L.height):
            for c in range(self.L.width):
                cell = self.g[r][c]
                if not cell.species or not cell.mature:
                    continue
                _, spec = self.rules_of(cell.species)
                if "shade_radius" not in spec:
                    continue
                rad = spec["shade_radius"]["value"]
                for dr in range(-rad, rad + 1):
                    for dc in range(-rad, rad + 1):
                        if self.inb(r + dr, c + dc):
                            self.shade[r + dr][c + dc] = 1

    # ---------- one tick ----------
    def step(self, plantings=()):
        L = self.L
        if self.tick in L.seasons:
            self.season = L.seasons[self.tick]
        if self.tick in L.events:
            self.events_fired.add(L.events[self.tick])

        # 1. your placements, capped at 20                       ASSUMPTION A6
        for idx, r, c in list(plantings)[:MAX_PER_TICK]:
            species = BY_INDEX[idx]["plant"]
            if species not in self.unlocked or not self.place(species, r, c):
                self.rejected += 1

        # 2. ageing and maturity
        for r in range(L.height):
            for c in range(L.width):
                cell = self.g[r][c]
                if not cell.species:
                    continue
                cell.age += 1
                g = self.growth_of(cell.species)
                _, matmul, _ = self.animal_mods(cell.species)
                weak, spec = self.rules_of(cell.species)
                ttm = g["time_to_maturity"] / max(matmul, 1e-6)
                nb = self.neighbours(r, c)
                if "adjacent_maturity_boost" in spec:
                    ttm -= spec["adjacent_maturity_boost"]["value"] * nb
                if "adjacent_maturity_penalty" in spec:
                    ttm += spec["adjacent_maturity_penalty"]["value"] * nb
                if "burnt_soil_maturity_boost" in spec and L.soil[r][c] == BURNT:
                    ttm -= spec["burnt_soil_maturity_boost"]["value"]
                cell.mature = cell.age >= max(1, ttm)

        self.recompute_shade()

        # 3. terrain effects from mature plants
        for r in range(L.height):
            for c in range(L.width):
                cell = self.g[r][c]
                if not (cell.species and cell.mature):
                    continue
                _, spec = self.rules_of(cell.species)
                if "burnt_soil_radius" in spec:
                    rad = spec["burnt_soil_radius"]["value"]
                    for dr in range(-rad, rad + 1):
                        for dc in range(-rad, rad + 1):
                            if self.inb(r + dr, c + dc) and (dr or dc):
                                L.soil[r + dr][c + dc] = BURNT

        # 4. spreading                                            ASSUMPTION A2
        births = []
        for r in range(L.height):
            for c in range(L.width):
                cell = self.g[r][c]
                if not (cell.species and cell.mature):
                    continue
                sp = cell.species
                g = self.growth_of(sp)
                weak, spec = self.rules_of(sp)
                if "no_winter_spread" in weak and self.season == "Winter":
                    continue
                if "no_shade_spread" in weak and self.shade[r][c]:
                    continue
                srm, _, rngm = self.animal_mods(sp)
                rate = max(1, round(g["spread_rate"] / srm))
                # ASSUMPTION A7: the spread clock counts the plant's own age, so
                # spread_rate is "ticks that must pass before it can spread".
                # Counting (tick - planted_tick) instead lets a plant spread on
                # the very tick you place it, which the spec does not suggest.
                if cell.age % rate != 0:
                    continue
                rng = max(1, int(g["spread_range"] * rngm))
                for dr, dc in pattern_offsets(g["spread_type"], rng):
                    tr, tc = r + dr, c + dc
                    if not self.inb(tr, tc) or self.g[tr][tc].species == sp:
                        continue
                    if "dead_matter_only_spread" in spec and not self.g[tr][tc].dead_matter:
                        continue
                    births.append((sp, tr, tc))
        for sp, r, c in births:
            self.place(sp, r, c)

        # 5. nutrients                                            ASSUMPTION A5
        for r in range(L.height):
            for c in range(L.width):
                cell = self.g[r][c]
                if cell.species:
                    cell.nutrients -= 0.5 if cell.dead_matter else 1.0
                    if cell.nutrients <= 0:
                        cell.nutrients = 0
                        self.kill(r, c)
                elif cell.dead_matter:
                    cell.nutrients = min(CELL_NUTRIENTS, cell.nutrients + 1.0)

        # 6. weakness deaths
        doomed = []
        for r in range(L.height):
            for c in range(L.width):
                cell = self.g[r][c]
                if not cell.species:
                    continue
                weak, spec = self.rules_of(cell.species)
                nb = self.neighbours(r, c)
                if "die_if_isolated" in weak and nb == 0:
                    doomed.append((r, c))
                elif ("die_if_neighbors_greater_than" in weak
                      and nb > weak["die_if_neighbors_greater_than"]["value"]):
                    doomed.append((r, c))
                elif ("no_shade_survival" in weak and self.shade[r][c]
                      and "can_grow_in_shade" not in spec):
                    doomed.append((r, c))
                elif "shade_required" in weak and not self.shade[r][c]:
                    doomed.append((r, c))
        for r, c in doomed:
            self.kill(r, c)

        # 7. animals, then current unlock eligibility             CONFIRMED A4
        w = self.world()
        self.animals = present_animals(w) if L.animals_enabled else set()
        w.animals = self.animals
        current_unlocks = unlocked_plants(w)
        newly = current_unlocks - self.unlocked
        if newly:
            self.log.append((self.tick, "UNLOCK", sorted(newly)))
        self.unlocked = current_unlocks

        self.tick += 1

    def run(self, actions: dict[int, list]):
        for t in range(self.L.ticks):
            self.step(actions.get(t, []))
        return self

    # ---------- scoring ----------
    def score(self, alpha: float = 1.0, k: float = 1.0) -> dict:
        counts = self.counts()
        C = sum(counts.values())
        Cmax = self.L.cells_total
        if C == 0:
            return {"final": 0.0, "main": 0.0, "H": 0.0, "size": 0.0,
                    "longevity": 0.0, "C": 0, "Cmax": Cmax, "species": 0,
                    "counts": {}, "animals": [], "unlocked": len(self.unlocked)}

        H = 0.0
        for n in counts.values():
            p = n / C
            H -= p * math.log(p) / math.log(N_SPECIES)

        size = (C / Cmax) ** alpha
        main = H * size
        T = self.L.ticks
        lon = sum((cell.age / T) ** k
                  for row in self.g for cell in row if cell.species) / Cmax

        return {
            "final": 0.8 * main + 0.2 * lon,
            "main": main, "H": H, "size": size, "longevity": lon,
            "C": C, "Cmax": Cmax, "species": len(counts),
            "counts": dict(sorted(counts.items(), key=lambda x: -x[1])),
            "animals": sorted(self.animals),
            "unlocked": len(self.unlocked),
        }
