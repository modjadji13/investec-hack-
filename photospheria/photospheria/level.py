"""The world a simulation runs in: grid size, terrain, soil, seasons, events."""
from __future__ import annotations

import json
from pathlib import Path

from .catalogue import DATA_DIR, DIRT

# The level file uses integer terrain codes with no legend. This is the mapping
# in play, and it is an ASSUMPTION - probe_terrain.py resolves it empirically.
#   0 -> soil   the mud and clay beds
#   1 -> soil   the dirt frames
#   2 -> path   the lines at cols 10/20/30/40 (plants cannot spread onto paths)
# 4 appears in Levels 3 and 4. Its cells touch only each other and undefined
# ground - never clay - so it is NOT a water feature (the spec says water is
# always ringed by clay). Treated as stone: uninhabitable, and it satisfies
# Stone Reed's "rock_or_path" adjacency requirement.
TERRAIN_MAP = {0: "soil", 1: "soil", 2: "path", 3: "crack", 4: "stone"}

# Cells absent from the level file. "void" means nothing can grow there.
# If probe_t2 comes back non-zero, change this to "soil".
DEFAULT_TERRAIN = "soil"


class Level:
    def __init__(self, width=50, height=50, ticks=500, soil=None, terrain=None,
                 events=None, seasons=None, animals_enabled=True, defined=None):
        self.width, self.height, self.ticks = width, height, ticks
        self.soil = soil or [[DIRT] * width for _ in range(height)]
        self.terrain = terrain or [["soil"] * width for _ in range(height)]
        self.events = events or {}            # {tick: "Rain"}
        self.seasons = seasons or {0: "Spring"}
        self.animals_enabled = animals_enabled
        # every cell the file explicitly listed, as (row, col, terrain_code, soil)
        self.defined = defined or []

    # -- convenience -------------------------------------------------------
    @property
    def cells_total(self) -> int:
        """Cmax in the scoring formula: the WHOLE grid, habitable or not."""
        return self.width * self.height

    def is_soil(self, r, c) -> bool:
        return self.terrain[r][c] == "soil"

    def plantable_for(self, preferred_soil) -> list[tuple[int, int]]:
        """Cells a plant with this preferred_soil list could legally occupy."""
        return [(r, c) for r in range(self.height) for c in range(self.width)
                if self.is_soil(r, c) and self.soil[r][c] in preferred_soil]

    def beds(self, cells) -> list[list[tuple[int, int]]]:
        """Split a cell list into 4-connected components - the planting beds."""
        pool, seen, out = set(cells), set(), []
        for cell in sorted(pool):
            if cell in seen:
                continue
            comp, stack = [], [cell]
            seen.add(cell)
            while stack:
                r, c = stack.pop()
                comp.append((r, c))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (r + dr, c + dc)
                    if n in pool and n not in seen:
                        seen.add(n)
                        stack.append(n)
            out.append(sorted(comp))
        return out


def load_level(path="level1.json") -> Level:
    p = Path(path)
    if not p.exists():
        p = DATA_DIR / path
    with open(p) as fh:
        d = json.load(fh)

    R, C = d["rows"], d["cols"]
    terrain = [[DEFAULT_TERRAIN] * C for _ in range(R)]
    soil = [[DIRT] * C for _ in range(R)]
    defined = []
    for cell in d["cells"]:
        r, c = cell["row"], cell["col"]
        terrain[r][c] = TERRAIN_MAP.get(cell["terrain"], "void")
        soil[r][c] = cell["soil"]
        defined.append((r, c, cell["terrain"], cell["soil"]))

    seasons, events = {}, {}
    for cmd in d.get("commands", []):
        if cmd["type"] == "season":
            seasons[cmd["tick"]] = cmd["season"]
        elif cmd["type"] in ("event", "weather"):
            events[cmd["tick"]] = cmd.get("event") or cmd.get("weather")
    seasons.setdefault(0, "Spring")

    return Level(width=C, height=R, ticks=d["ticks"], soil=soil, terrain=terrain,
                 events=events, seasons=seasons,
                 animals_enabled=d.get("animals_enabled", True), defined=defined)
