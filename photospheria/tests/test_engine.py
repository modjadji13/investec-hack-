"""Mechanics tests. These pin the engine's behaviour to the problem statement.

When you change an ASSUMPTION in engine.py, a test here should change with it.
If you change one and NOTHING fails, the assumption wasn't actually being used
and that is worth knowing too.
"""
import math

import pytest

from photospheria import Level, Simulator, pattern_offsets
from photospheria.catalogue import BY_NAME, N_SPECIES
from photospheria.engine import CELL_NUTRIENTS

GRASS = BY_NAME["Grass"]["index"]
OAK = BY_NAME["Oak Tree"]["index"]
MOSS = BY_NAME["Blue Moss"]["index"]
ROSE = BY_NAME["Rose Bush"]["index"]


def flat(size=20, ticks=200):
    """An empty dirt field with no seasons or events - a clean test bench."""
    return Level(width=size, height=size, ticks=ticks)


# --------------------------------------------------------------- spread shapes
@pytest.mark.parametrize("kind,rng,expected", [
    ("VonNeumann", 1, 4), ("VonNeumann", 2, 8),
    ("Moore", 1, 8), ("Moore", 2, 24),
    ("Row", 1, 2), ("Column", 3, 6),
    ("CrossHatch", 1, 4), ("CrossHatch", 2, 8),
])
def test_pattern_sizes(kind, rng, expected):
    assert len(pattern_offsets(kind, rng)) == expected


def test_moore_includes_diagonals_von_neumann_does_not():
    assert (1, 1) in pattern_offsets("Moore", 1)
    assert (1, 1) not in pattern_offsets("VonNeumann", 1)


def test_row_is_horizontal_column_is_vertical():
    assert all(dr == 0 for dr, _ in pattern_offsets("Row", 2))
    assert all(dc == 0 for _, dc in pattern_offsets("Column", 2))


def test_unknown_pattern_raises():
    with pytest.raises(ValueError):
        pattern_offsets("Spiral", 1)


# ------------------------------------------------------------------- nutrients
def test_cell_starts_at_full_nutrients():
    sim = Simulator(flat())
    assert sim.g[0][0].nutrients == CELL_NUTRIENTS


def test_plant_dies_exactly_100_ticks_after_planting():
    """The single most important number on Level 1: a cell is a 100-tick lease."""
    sim = Simulator(flat(size=3, ticks=150))
    sim.step([(GRASS, 1, 1)])
    for _ in range(98):
        sim.step()
    assert sim.g[1][1].species == "Grass", "should still be alive at tick 99"
    sim.step()
    assert sim.g[1][1].species is None, "should be dead by tick 100"
    assert sim.g[1][1].dead_matter is True


def test_dead_matter_regains_nutrients_while_empty():
    sim = Simulator(flat(size=3, ticks=150))
    sim.g[1][1].dead_matter = True
    sim.g[1][1].nutrients = 10.0
    sim.step()
    assert sim.g[1][1].nutrients == 11.0


def test_nutrients_cap_at_100():
    sim = Simulator(flat(size=3))
    sim.g[1][1].dead_matter = True
    sim.g[1][1].nutrients = CELL_NUTRIENTS
    sim.step()
    assert sim.g[1][1].nutrients == CELL_NUTRIENTS


# -------------------------------------------------------------------- maturity
def test_grass_matures_in_one_tick_and_then_spreads():
    sim = Simulator(flat(size=9))
    sim.step([(GRASS, 4, 4)])
    assert sim.g[4][4].mature, "Grass has time_to_maturity 1"
    before = sum(1 for row in sim.g for c in row if c.species)
    for _ in range(3):
        sim.step()
    after = sum(1 for row in sim.g for c in row if c.species)
    assert after > before, "a mature Grass must spread"


def test_oak_does_not_spread_before_maturity():
    sim = Simulator(flat(size=15))
    sim.step([(OAK, 7, 7)])
    for _ in range(15):                     # Oak matures at 20
        sim.step()
    assert sum(1 for row in sim.g for c in row if c.species) == 1


# ------------------------------------------------------------------ weaknesses
def test_blue_moss_dies_with_more_than_four_neighbours():
    """The Level 2+ bottleneck: Blue Moss gates a third of the tech tree."""
    sim = Simulator(flat(size=9, ticks=50))
    sim.unlocked.add("Blue Moss")
    for r in range(3, 6):
        for c in range(3, 6):
            sim.place("Blue Moss", r, c)
    assert sim.neighbours(4, 4) == 8
    sim.step()
    assert sim.g[4][4].species is None, "interior moss has 8 neighbours, must die"


def test_blue_moss_survives_at_exactly_four_neighbours():
    sim = Simulator(flat(size=9, ticks=50))
    sim.unlocked.add("Blue Moss")
    sim.place("Blue Moss", 4, 4)
    for r, c in ((3, 3), (3, 5), (5, 3), (5, 5)):       # 4 diagonal neighbours
        sim.place("Grass", r, c)
    assert sim.neighbours(4, 4) == 4
    sim.step()
    assert sim.g[4][4].species == "Blue Moss", "the limit is >4, so 4 is fine"


def test_blue_moss_smothers_itself_on_a_checkerboard():
    """A checkerboard looks safe - every cell has exactly 4 diagonal neighbours.
    It isn't: adjacent_maturity_boost makes Blue Moss mature almost instantly
    next to company, it then spreads into its own gaps, and the whole patch
    crosses the 4-neighbour limit and dies. Spacing has to be wider than this."""
    sim = Simulator(flat(size=13, ticks=50))
    sim.unlocked.add("Blue Moss")
    for r in range(2, 11):
        for c in range(2, 11):
            if (r + c) % 2 == 0:
                sim.place("Blue Moss", r, c)
    planted = sum(1 for row in sim.g for c in row if c.species)
    for _ in range(8):
        sim.step()
    alive = sum(1 for row in sim.g for c in row if c.species)
    assert alive < planted / 2


def test_grass_cannot_be_placed_in_shade():
    sim = Simulator(flat(size=15, ticks=60))
    sim.step([(OAK, 7, 7)])
    for _ in range(21):                     # let the Oak mature and cast shade
        sim.step()
    assert sim.shade[7][8] == 1
    assert sim.can_occupy("Grass", 7, 8) is False


# -------------------------------------------------------------------- placement
def test_cannot_plant_on_wrong_soil():
    lvl = flat(size=5)
    lvl.soil[2][2] = 2                      # clay; no starter accepts it
    sim = Simulator(lvl)
    assert sim.place("Grass", 2, 2) is False


def test_cannot_plant_on_path_or_void():
    lvl = flat(size=5)
    lvl.terrain[1][1] = "path"
    lvl.terrain[2][2] = "void"
    sim = Simulator(lvl)
    assert sim.place("Grass", 1, 1) is False
    assert sim.place("Grass", 2, 2) is False


def test_locked_species_placements_are_rejected_not_crashed():
    sim = Simulator(flat(size=5))
    sim.step([(MOSS, 2, 2)])                # Blue Moss is locked at the start
    assert sim.g[2][2].species is None
    assert sim.rejected == 1


def test_only_first_twenty_plantings_per_tick_are_used():
    sim = Simulator(flat(size=30))
    # Oak matures in 20 ticks, so nothing can spread and confuse the count
    sim.step([(OAK, 0, c) for c in range(25)])
    assert sum(1 for c in sim.g[0] if c.species) == 20


def test_a_plant_does_not_spread_on_the_tick_it_is_placed():
    """ASSUMPTION A7. Grass matures in 1 tick and spreads every 2; it must not
    do both on the tick you place it."""
    sim = Simulator(flat(size=9))
    sim.step([(GRASS, 4, 4)])
    assert sum(1 for row in sim.g for c in row if c.species) == 1


def test_manual_placement_overwrites_an_existing_plant():
    sim = Simulator(flat(size=5))
    sim.step([(GRASS, 2, 2)])
    sim.step([(ROSE, 2, 2)])
    assert sim.g[2][2].species == "Rose Bush"
    assert sim.g[2][2].age == 1, "overwriting resets the plant's age"


# ---------------------------------------------------------------------- scoring
def test_empty_grid_scores_zero():
    assert Simulator(flat()).score()["final"] == 0.0


def test_monoculture_has_zero_diversity():
    """This is what makes a pure-Grass probe useful: H is exactly 0, so the
    leaderboard number it returns is purely the longevity term."""
    sim = Simulator(flat(size=10))
    for c in range(10):
        sim.place("Grass", 0, c)
    assert sim.score()["H"] == pytest.approx(0.0)


def test_entropy_uses_log_base_31():
    sim = Simulator(flat(size=10))
    for i, name in enumerate(["Grass", "Rose Bush", "Lavender", "Dwarf Sunflower"]):
        for c in range(5):
            sim.place(name, i, c)
    expected = math.log(4) / math.log(N_SPECIES)
    assert sim.score()["H"] == pytest.approx(expected, abs=1e-9)


def test_cmax_is_the_whole_grid_not_just_habitable_cells():
    lvl = flat(size=10)
    for r in range(10):
        for c in range(5, 10):
            lvl.terrain[r][c] = "void"
    sim = Simulator(lvl)
    assert sim.score()["Cmax"] == 100


def test_alpha_and_k_are_tunable():
    sim = Simulator(flat(size=10))
    for c in range(10):
        sim.place("Grass", 0, c)
        sim.place("Lavender", 1, c)
    a1 = sim.score(alpha=1.0)["size"]
    a2 = sim.score(alpha=0.5)["size"]
    assert a2 > a1, "a smaller alpha is kinder to a partly full grid"
