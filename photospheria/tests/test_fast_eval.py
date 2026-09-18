"""Differential tests for the accelerated experimental evaluator."""
import random
import pytest

np=pytest.importorskip('numpy')
pytest.importorskip('numba')
from photospheria.fast_eval import FastSimulator
from photospheria.engine import Simulator
from photospheria.level import Level
from photospheria.strategies import level_copy
from photospheria.catalogue import BY_NAME, BY_INDEX


def test_fast_engine_matches_all_species_on_mixed_terrain():
    rng=random.Random(814)
    level=Level(width=9,height=8,ticks=70,
                soil=[[rng.randrange(4) for _ in range(9)] for _ in range(8)],
                terrain=[[rng.choice(['soil']*8+['water','stone','path','crack']) for _ in range(9)] for _ in range(8)],
                seasons={0:'Spring',15:'Summer',30:'Autumn',50:'Winter'},
                events={3:'Rain',25:'Drought'})
    reference=Simulator(level_copy(level))
    fast=FastSimulator(level_copy(level))
    reference.unlocked=set(BY_NAME);fast.unlocked=set(BY_NAME)
    # Lower nutrients exercise death and regrowth during the short test.
    for r in range(8):
        for c in range(9):
            nutrient=float(rng.randrange(1,40))
            reference.g[r][c].nutrients=nutrient
            fast.nut[r*9+c]=nutrient
    for t in range(70):
        actions=[(rng.choice(list(BY_INDEX)),rng.randrange(8),rng.randrange(9)) for _ in range(20)]
        reference.step(actions);fast.step(actions)
        cells=[c for row in reference.g for c in row]
        species=[BY_NAME[c.species]['index'] if c.species else 0 for c in cells]
        assert np.array_equal(fast.sp,species),t
        assert np.array_equal(fast.age,[c.age for c in cells]),t
        assert np.array_equal(fast.nut,[c.nutrients for c in cells]),t
        assert np.array_equal(fast.dead,[c.dead_matter for c in cells]),t
        assert np.array_equal(fast.sub,[BY_NAME[c.sub]['index'] if c.sub else 0 for c in cells]),t
        assert reference.rejected==fast.rejected
        assert reference.animals==fast.animals
        assert np.array_equal(fast.shade,np.array(reference.shade).ravel())
        assert np.array_equal(fast.soil,np.array(reference.L.soil).ravel())
    assert reference.score()['final']==pytest.approx(fast.score()['final'])
