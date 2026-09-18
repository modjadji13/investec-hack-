# Photospheria optimized submissions

These files were searched and evaluated against the local simulator supplied
with the project. The level files and four resource JSON files match the files
provided with the challenge.

## Real judge results - 2026-09-12

The real judge disproved the local predictions for Levels 2 and 3. Do not use
those two experimental candidates. Keep the Level 4 candidate, which produced a
confirmed improvement.

| Level | Previous judge score | Candidate judge score | Decision |
|---|---:|---:|---|
| 1 | 222,745,174 | 222,745,174 | Keep original |
| 2 | 284,416,228 | 187,985,678 | Roll back |
| 3 | 208,970,159 | 153,208,357 | Roll back |
| 4 | 204,979,123 | 260,868,897 | Keep candidate |

The confirmed-best combination totals 977,000,458: original Levels 1-3 and
optimized Level 4. The currently submitted combination totals 824,808,106, so
rolling back Levels 2 and 3 restores 152,192,352 points.

| Level | Current local score | Candidate local score | Change | Candidate fill | Species |
|---|---:|---:|---:|---:|---:|
| 1 | 0.309615 | 0.309615 | 0.0% | 1,980 / 2,500 | 5 |
| 2 | 0.340396 | 0.401365 | +17.9% | 6,535 / 7,000 | 8 |
| 3 | 0.235657 | 0.374361 | +58.9% | 19,834 / 22,500 | 6 |
| 4 | 0.211764 | 0.402513 | +90.1% | 56,969 / 60,000 | 6 |

The candidates passed the submission schema checks and local simulator, but the
real judge showed that the Level 2 and Level 3 candidates are regressions. The
judge is authoritative, so those two candidates must not be submitted again.

The leaderboard score cannot be predicted exactly because alpha, k, and the
large scaling constant are hidden. Across alpha values 0.5, 1, 2 and 3 and k
values 0.5, 1 and 2, the candidates improved over the originals in every tested
case. The gains also remained positive when retaining dead matter under replants
and when adding mature-plant invasiveness competition.

Real judge results:

| Level | Proven baseline | Candidate | Decision |
|---|---:|---:|---|
| 1 | 222,745,174 | 222,745,174 | Keep baseline |
| 2 | 284,416,228 | 187,985,678 | Roll back to baseline |
| 3 | 208,970,159 | 153,208,357 | Roll back to baseline |
| 4 | 204,979,123 | 260,868,897 | Keep candidate |

The confirmed-best combination totals **977,000,458**: baseline Levels 1-3
plus optimized Level 4. The clean upload files are in `out/confirmed-best` and
`out/Photospheria-confirmed-best-submissions.zip`.

Files:

- `LEVEL1_CONFIRMED_222745174.json`: proven Level 1 baseline.
- `LEVEL2_ROLLBACK_284416228.json`: proven Level 2 baseline.
- `LEVEL3_ROLLBACK_208970159.json`: proven Level 3 baseline.
- `LEVEL4_CONFIRMED_260868897.json`: improved Level 4 candidate.
