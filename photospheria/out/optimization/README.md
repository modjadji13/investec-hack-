# Photospheria optimized submissions

These files were searched and evaluated against the local simulator supplied
with the project. The level files and four resource JSON files match the files
provided with the challenge.

| Level | Current local score | Candidate local score | Change | Candidate fill | Species |
|---|---:|---:|---:|---:|---:|
| 1 | 0.309615 | 0.309615 | 0.0% | 1,980 / 2,500 | 5 |
| 2 | 0.340396 | 0.401365 | +17.9% | 6,535 / 7,000 | 8 |
| 3 | 0.235657 | 0.374361 | +58.9% | 19,834 / 22,500 | 6 |
| 4 | 0.211764 | 0.402513 | +90.1% | 56,969 / 60,000 | 6 |

The candidates passed the submission schema checks. Levels 2, 3 and 4 were
also replayed through the original Python engine with zero rejected placements;
their scores match the faster evaluator. Level 1 is the supplied submission and
was already verified.

The leaderboard score cannot be predicted exactly because alpha, k, and the
large scaling constant are hidden. Across alpha values 0.5, 1, 2 and 3 and k
values 0.5, 1 and 2, the candidates improved over the originals in every tested
case. The gains also remained positive when retaining dead matter under replants
and when adding mature-plant invasiveness competition.

If the leaderboard combines normalized level scores with equal scaling, the
local sum improves by 35.6%, which would project 921,110,684 to about
1,248,804,661. This is an estimate, not a guaranteed judge score. Submit one
level at a time and keep the previous accepted file available for rollback.

Files:

- `LEVEL1_optimized.json`: unchanged supplied Level 1 submission.
- `LEVEL2_optimized.json`: eight final species, late diversification.
- `LEVEL3_optimized.json`: six winter-capable species.
- `LEVEL4_optimized.json`: six winter-capable species.
