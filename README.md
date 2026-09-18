# Photospheria

Photospheria simulation, level data, search tools, submissions, and a replay
viewer for all four levels of the Investec hackathon challenge.

The project is in `photospheria/`. Open that folder in VS Code to use its
existing launch configurations.

## Run

Install Python 3.9 or newer, then run from the repository root:

```powershell
cd photospheria
python run.py info
python run.py all
start out\all-levels.html
```

The four-level viewer is also included at `photospheria/out/all-levels.html`.
The base simulator uses the Python standard library. For tests, install
`requirements.txt`; the optional fast evaluator also needs NumPy and Numba:

```powershell
python -m pip install -r requirements.txt numpy numba
python -m pytest
```

## Files

- `photospheria/photospheria/`: simulation engine, fast evaluator, strategies,
  and rendering.
- `photospheria/data/`: four levels, plant and animal catalogues, and original
  submissions.
- `photospheria/tests/`: existing test suite.
- `photospheria/out/confirmed-best/`: submissions with recorded judge scores.
- `photospheria/out/judge-calibrated/`: experimental follow-up submissions.
- `photospheria/tools/`: judge-log analysis and candidate generation scripts.

The recorded best scores from September 12, 2026 total **977,000,458**:
Level 1: 222,745,174; Level 2: 284,416,228; Level 3: 208,970,159;
Level 4: 260,868,897.

The local simulator is an approximation of the official judge. Local scores
do not guarantee official improvements; the follow-up submissions have not
been confirmed by the supplied judge results. The log tools currently refer
to the original Windows Downloads paths and require those evaluation logs.

See `photospheria/README.md` for the original simulator documentation; some
of its assumptions predate the later judge results.
