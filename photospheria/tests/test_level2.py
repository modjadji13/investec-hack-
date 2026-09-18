"""Coverage for the four-level bundle and its supplied submissions."""
import json
from pathlib import Path

from photospheria import load_level
from photospheria.submission import from_submission, validate
from photospheria.level2 import solve_with_tech


DATA = Path(__file__).resolve().parents[1] / "data"


def test_all_four_level_dimensions():
    expected = [(50, 50, 500), (100, 70, 500),
                (150, 150, 800), (300, 200, 800)]
    actual = []
    for number in range(1, 5):
        level = load_level(DATA / f"level{number}.json")
        actual.append((level.width, level.height, level.ticks))
    assert actual == expected


def test_all_four_supplied_submissions_are_valid():
    for number in range(1, 5):
        level = load_level(DATA / f"level{number}.json")
        doc = json.loads((DATA / f"level{number}_submission.json").read_text())
        actions = from_submission(doc)
        assert validate(actions, level) == []
        assert max(actions) == level.ticks - 1


def test_updated_level2_solver_is_available():
    assert callable(solve_with_tech)
