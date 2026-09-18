# Judge-calibrated submissions

The official logs confirm that unlock eligibility is recalculated while the
simulation runs. It is not sticky. A species placement can work during one
animal/event window and fail later when that condition disappears.

## Confirmed results

| Level | Proven score | Candidate score | Key evidence |
|---|---:|---:|---|
| 1 | 222,745,174 | same | 0 rejected placements; final counts 329/171/210/98/992 |
| 2 | 284,416,228 | 187,985,678 | candidate lost all 312 Ironthorn attempts to unlock failures |
| 3 | 208,970,159 | 153,208,357 | 472 Crimson, 19 Crystal Cactus and 19 Razorgrass attempts failed unlock checks |
| 4 | 204,979,123 | 260,868,897 | improved despite 538 unlock failures |

## Next submission order

1. `LEVEL4_FIX_REJECTED_WITH_SUNFLOWER.json`: replaces the 538 exact
   placements that the official Level 4 log rejected for unlock failures with
   starter Dwarf Sunflower. All other actions remain unchanged.
2. `LEVEL3_PROBE_RAZOR_10.json`: the proven 208.97M baseline with only ten
   Lavender placements changed to Razorgrass during ticks 765-768, a window in
   which the judge accepted Razorgrass in the previous run.
3. `LEVEL2_PROBE_ORANGE_20.json`: the proven 284.42M baseline with only twenty
   Rose placements changed to Orange Blossom during its judge-confirmed window.

Submit one file at a time and save its evaluation log before proceeding. The
Level 2 and Level 3 files are deliberately small probes; restore the proven
baseline if either score falls.
