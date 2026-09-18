# Photospheria — local simulator

A working replica of the Hack&lt;IT&gt; *Root Cause Analysis* engine, plus a solver
for Level 1. Pure standard library — nothing to install to run the simulator.

```bash
python3 run.py info      # what the level file actually contains, with a map
python3 run.py tree      # which of the 31 species are reachable, and how
python3 run.py watch     # play a run in your terminal, in colour
python3 run.py solve     # tune a strategy and write out/submission.json
python3 run.py replay    # write out/replay.html — scrub through a run in a browser
python3 -m pytest        # 50 tests pinning the mechanics to the spec
```

Open the folder in VS Code and press **F5** — the launch configs cover every
command above, including a "watch the bad baseline fail" run which is the
fastest way to understand why the good strategy looks the way it does.

## Setup

```bash
cd photospheria
python3 -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt                      # only needed for pytest
python3 run.py info
```

Python 3.9+. In VS Code, pick the interpreter with **Ctrl/Cmd+Shift+P →
Python: Select Interpreter**, then the Testing tab will discover the suite.

## What's in here

| file | what it does |
|---|---|
| `photospheria/catalogue.py` | loads the four data files; evaluates unlock and animal condition trees |
| `photospheria/level.py` | parses the level file into a grid of terrain and soil |
| `photospheria/engine.py` | **the simulation** — maturity, spread, nutrients, shade, death, animals, scoring |
| `photospheria/strategies.py` | planting strategies, including the tuning loop |
| `photospheria/render.py` | terminal renderer and the HTML replay |
| `photospheria/submission.py` | reads/writes the submission JSON and validates it |
| `run.py` | the command line |
| `tests/` | 50 tests — mechanics in `test_engine.py`, level-specific facts in `test_level1.py` |

## What the solver knows about Level 1

Run `python3 run.py info` and it prints all of this from the file itself. The
short version:

**It's a greenhouse.** Six rectangular beds separated by path lines at columns
10, 20, 30 and 40. Only 1060 of the 2500 cells are defined; rows 20–29 and the
outer margins are empty.

**Only five species exist here.** `animals_enabled` is false and no weather
events fire, and every one of the other 26 unlocks needs an animal or an event
somewhere in its chain. So you have Grass, Rose Bush, Lavender, Dwarf Sunflower
and Oak Tree, and diversity is capped at log(5)/log(31) = **0.4687**.

**The clay beds are decoys.** All five species accept soil `[0,1]` — Dirt and
Mud. Nothing available grows in clay, so 360 cells are permanently dead. Only
**540 cells** are plantable, and since Cmax is the whole 2500-cell grid, fill is
capped at 21.6%.

**A cell is a 100-tick lease.** It loses one nutrient per tick while occupied
and only recovers while empty, so anything planted before tick 401 is a corpse
by scoring time. That leaves ticks 401–499: 99 × 20 = **1980 placements for 540
cells**. You never need spreading. You hand-place the entire final grid.

## The strategy, and why it's shaped that way

Four attempts, each fixing what the last one revealed:

| approach | score | what went wrong |
|---|---|---|
| even scatter from tick 0 | 0.020 | Grass reached 89% of the garden |
| slowest-maturing species placed first | 0.047 | Rose Bush crept along rows instead |
| restricted to plantable cells only | 0.051 | Oak and Sunflower vanished entirely |
| **contiguous block per species** | 0.074 | scattered cells get eaten by neighbours |
| **+ block sizes tuned against the loss** | **0.082** | — |

Final mix is within 1% of a perfect five-way split. The two ideas doing the
work: **plant as late as the schedule fits**, and **give each species a
contiguous strip** — a lone cell surrounded by other species is overwritten the
moment one of them matures, but a block only loses its boundary.

`strategies.tune()` is the whole optimisation, and it isn't a search. It runs
the sim, sees which species lost cells at their boundaries, widens their strips,
and repeats. Nine rounds gets within a rounding error of the ceiling.

## This is a replica, and replicas are wrong

The real engine is hidden. Every guess is marked `ASSUMPTION` in `engine.py`:

| | assumption | how to test it |
|---|---|---|
| A1 | CrossHatch spreads on the diagonals | change it, see if the score moves |
| A2 | spread resolves in row-major order | matters because last writer wins |
| A3 | coverage is denominated by the whole grid | the spec says Cmax = N × M |
| A4 | unlocks are sticky once earned | only matters from Level 2 |
| A5 | a plant on dead matter drains 0.5/tick | literal reading of the spec |
| A6 | your placements resolve before spreading | affects the final tick most |
| A7 | the spread clock counts the plant's own age | a test caught this one |

There's one more that isn't in the engine but matters more than all of them:
**`level.py` treats the 1440 undefined cells as void.** If they're actually
plain dirt, the plantable area goes from 540 to ~1980 and the ceiling roughly
quadruples. Change `DEFAULT_TERRAIN` to `"soil"` and rerun to see the
difference. Resolve it with a probe submission before trusting any of these
numbers.

## Calibrating against the leaderboard

The submission score is your raw score times a large hidden constant. You know
your raw score locally, so one submission gives you the constant — and then
every other team's score becomes readable:

```
constant    = your_board_score / your_local_score
leader_raw  = leader_board_score / constant
```

If `leader_raw` comes out above about **0.090**, the leader is scoring beyond
what 540 cells allows, which means the undefined cells are in play and this
solver is working on a quarter of the map.

A local score you haven't checked against their engine is just a confident
guess. Submit early, compare, then trust it.
