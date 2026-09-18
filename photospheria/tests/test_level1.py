"""Tests about the actual Level 1 file and the strategy built for it."""
import math

import pytest

from photospheria import Simulator, load_level, strategies, submission
from photospheria.catalogue import (BY_NAME, N_SPECIES, PLANTS, STARTERS,
                                    UNLOCK_BY_NAME, ANIMAL_BY_NAME)
from photospheria.engine import MAX_PER_TICK


@pytest.fixture(scope="module")
def lvl():
    return load_level("data/level1.json")


# ------------------------------------------------------------- the level file
def test_level_dimensions(lvl):
    assert (lvl.width, lvl.height, lvl.ticks) == (50, 50, 500)
    assert lvl.cells_total == 2500


def test_level_1_has_no_animals_and_no_weather(lvl):
    assert lvl.animals_enabled is False
    assert lvl.events == {}


def test_seasons_switch_every_hundred_ticks(lvl):
    assert lvl.seasons == {0: "Spring", 100: "Summer", 200: "Autumn",
                           300: "Winter", 400: "Spring"}


def test_scoring_window_is_spring(lvl):
    """Rose Bush and Lavender cannot spread in Winter. Winter ends at 400 and
    the plants that get scored are all placed after that, so it costs nothing."""
    last = max(t for t in lvl.seasons if t <= lvl.ticks)
    assert lvl.seasons[last] == "Spring"


def test_only_1060_of_2500_cells_are_defined(lvl):
    assert len(lvl.defined) == 1060


# --------------------------------------------------------- what can grow where
def test_no_level_1_species_accepts_clay():
    """360 clay cells are decoys - only Mire Bloom takes soil 2, and it needs
    Rain plus Blue Moss, neither of which exists on this level."""
    for name in STARTERS:
        assert 2 not in BY_NAME[name]["preferred_soil"]


def test_plantable_area_is_1980_cells(lvl):
    """CORRECTED BY THE LEADERBOARD. This test used to assert 540, on the
    assumption that the 1440 cells absent from the level file were void. A
    submission scoring 71M against a leader at 1.28B disproved it: an 18x
    spread is impossible if everyone is capped at 540 cells. The undefined
    cells are plain dirt - they are simply the default and so not listed."""
    assert len(strategies.plantable_cells(lvl)) == 1980


def test_plantable_cells_form_one_connected_field(lvl):
    """With the undefined cells in play the six separate beds join up into one
    field - the paths no longer isolate them."""
    beds = lvl.beds(strategies.plantable_cells(lvl))
    assert sorted(len(b) for b in beds) == [1980]


def test_only_five_species_are_reachable_without_animals(lvl):
    """Every other unlock needs an animal or a weather event somewhere in its
    chain, and Level 1 has neither."""
    have = set(STARTERS)

    def reachable(node):
        if "op" in node:
            if node["op"] == "AND":
                return all(reachable(c) for c in node["children"])
            if node["op"] == "OR":
                return any(reachable(c) for c in node["children"])
            return True
        t = node["type"]
        if t == "species_absent":
            return True
        if t == "species_present":
            return False if node["species"] in ANIMAL_BY_NAME else node["species"] in have
        if t in ("coverage", "count"):
            return node["plant"] in have
        if t == "event":
            return False
        return True

    while True:
        newly = [p["plant"] for p in PLANTS if p["plant"] not in have
                 and (p["plant"] not in UNLOCK_BY_NAME
                      or reachable(UNLOCK_BY_NAME[p["plant"]]))]
        if not newly:
            break
        have |= set(newly)
    assert have == set(STARTERS)


def test_diversity_ceiling_for_five_species():
    assert math.log(5) / math.log(N_SPECIES) == pytest.approx(0.4687, abs=1e-4)


# ------------------------------------------------------------------- budgeting
def test_safe_planting_window(lvl):
    """Plant before this tick and the plant is dead before it can be scored."""
    assert strategies.safe_planting_tick(lvl) == 401


def test_budget_exactly_covers_the_plantable_area(lvl):
    """99 usable ticks x 20 placements = 1980, for exactly 1980 plantable
    cells. The budget fits the map precisely, with no slack at all."""
    budget = (lvl.ticks - strategies.safe_planting_tick(lvl)) * MAX_PER_TICK
    assert budget == 1980
    assert budget == len(strategies.plantable_cells(lvl))


# ------------------------------------------------------------------- strategy
@pytest.fixture(scope="module")
def blocks_run(lvl):
    actions = strategies.late_blocks(strategies.level_copy(lvl))
    sim = Simulator(strategies.level_copy(lvl)).run(actions)
    return actions, sim.score()


def test_block_strategy_places_everything_in_the_safe_window(blocks_run, lvl):
    actions, _ = blocks_run
    assert min(actions) >= strategies.safe_planting_tick(lvl)
    assert max(actions) <= lvl.ticks - 1


def test_block_strategy_is_a_valid_submission(blocks_run, lvl):
    actions, _ = blocks_run
    assert submission.validate(actions, lvl) == []
    assert all(len(v) <= MAX_PER_TICK for v in actions.values())


def test_block_strategy_fills_every_plantable_cell(blocks_run, lvl):
    _, score = blocks_run
    assert score["C"] == len(strategies.plantable_cells(lvl))


def test_block_strategy_keeps_all_five_species_alive(blocks_run):
    _, score = blocks_run
    assert score["species"] == 5


def test_level2_unlocks_far_more_species_than_level1():
    """Level 2 turns animals on and fires Rain, which opens 29 of 31 species
    and more than doubles the diversity ceiling. That is where the score is."""
    import math
    from photospheria.catalogue import N_SPECIES
    assert math.log(29) / math.log(N_SPECIES) > 0.98
    assert math.log(5) / math.log(N_SPECIES) < 0.47


def test_blocks_beat_the_naive_baseline(lvl):
    """The naive strategy scatters an even mix from tick 0 and lets it grow.
    It loses badly - the fastest spreader eats everything. That gap is the
    entire point of the block strategy."""
    naive = Simulator(strategies.level_copy(lvl)).run(
        strategies.naive_even(strategies.level_copy(lvl))).score()
    blocks = Simulator(strategies.level_copy(lvl)).run(
        strategies.late_blocks(strategies.level_copy(lvl))).score()
    assert blocks["final"] > naive["final"] * 2


def test_round_trip_through_the_submission_format(lvl):
    actions = strategies.late_blocks(strategies.level_copy(lvl))
    doc = submission.to_submission(actions)
    assert set(doc) == {"actions"}
    assert all(set(a) == {"tick", "plants"} for a in doc["actions"])
    assert all(set(p) == {"plant_index", "row", "col"}
               for a in doc["actions"] for p in a["plants"])
    assert submission.from_submission(doc) == actions
