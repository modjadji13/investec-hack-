"""Photospheria — a local replica of the Hack<IT> Root Cause Analysis engine."""
from .catalogue import BY_INDEX, BY_NAME, PLANTS, STARTERS, N_SPECIES
from .engine import Simulator, MAX_PER_TICK, pattern_offsets
from .level import Level, load_level
from . import strategies, render, submission

__all__ = ["Simulator", "Level", "load_level", "strategies", "render",
           "submission", "BY_NAME", "BY_INDEX", "PLANTS", "STARTERS",
           "N_SPECIES", "MAX_PER_TICK", "pattern_offsets"]
