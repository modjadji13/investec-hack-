"""Hill-climb the balanced_plan parameters from the best known candidate.

optimize_levels.py sampled 12 uniform-random parameter sets per level. At
~0.4s per evaluation that leaves most of the space untouched. This starts from
the winner and perturbs one thing at a time, keeping any improvement.

    python3 hillclimb.py --level 3 --minutes 5
"""
import argparse, copy, json, random, time
from pathlib import Path
from photospheria import load_level
from photospheria.submission import to_submission, validate
from optimize_levels import balanced_plan, robust_metrics, save_candidate

OUT = Path("out/optimization")
WINTER_SETS = [
    ["Grass", "Razorgrass", "Crimson Vine", "Crystal Cactus", "Dwarf Sunflower", "Oak Tree"],
    ["Grass", "Crimson Vine", "Dwarf Sunflower", "Oak Tree", "Crystal Cactus"],
]
OPTIONAL = ["Razorgrass", "Orange Blossom", "Ironthorn Shrub"]


def starting_params(n):
    p = json.load(open(OUT / f"LEVEL{n}_candidate_metrics.json")).get("params")
    if p and "species" in p:
        return p
    return {"species": WINTER_SETS[0], "weights": [1.0] * 6, "vertical": True,
            "window": 99, "strides": {s: 7 for s in WINTER_SETS[0]}, "topup": 50, "seed": 1}


def perturb(p, rng):
    q = copy.deepcopy(p)
    q.setdefault("strides", {}); q.setdefault("delays", {})
    q["weights"] = list(q.get("weights", [1.0] * len(q["species"])))
    while len(q["weights"]) < len(q["species"]):
        q["weights"].append(1.0)
    op = rng.choices(
        ["weight", "stride", "window", "topup", "delay", "vertical", "nursery", "species", "seed"],
        weights=[30, 25, 8, 8, 8, 3, 6, 6, 6])[0]
    sp = q["species"]
    if op == "weight":
        i = rng.randrange(len(sp)); q["weights"][i] *= rng.uniform(0.7, 1.4)
    elif op == "stride":
        s = rng.choice(sp); cur = q["strides"].get(s, 7)
        lo, hi = (15, 50) if s in ("Crimson Vine",) else (3, 15)
        q["strides"][s] = max(lo, min(hi, cur + rng.choice([-3, -2, -1, 1, 2, 3])))
    elif op == "window":
        q["window"] = max(85, min(140, q.get("window", 99) + rng.choice([-8, -4, 4, 8])))
    elif op == "topup":
        q["topup"] = max(15, min(90, q.get("topup", 50) + rng.choice([-10, -5, 5, 10])))
    elif op == "delay":
        s = rng.choice(sp); q["delays"][s] = rng.choice([0, 0, 10, 20, 30])
    elif op == "vertical":
        q["vertical"] = not q.get("vertical", True)
    elif op == "nursery":
        q["nursery"] = rng.choice([0, 0, 0.04, 0.08, 0.12])
        q["nursery_window"] = rng.choice([150, 190, 230])
    elif op == "species":
        cand = [s for s in OPTIONAL if s not in sp]
        if sp and len(sp) > 4 and rng.random() < 0.4:
            i = rng.randrange(len(sp)); sp.pop(i); q["weights"].pop(i)
        elif cand:
            s = rng.choice(cand); sp.append(s); q["weights"].append(1.0)
            q["strides"].setdefault(s, 7)
    elif op == "seed":
        q["seed"] = rng.randrange(10_000)
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, required=True)
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--restarts", type=int, default=3)
    args = ap.parse_args()

    n = args.level
    level = load_level(f"data/level{n}.json")
    rng = random.Random(n * 1000 + 7)
    best_p = starting_params(n)
    acts, sim = balanced_plan(level, best_p)
    best = sim.score()["final"]
    best_acts, best_sim = acts, sim
    print(f"L{n} start {best:.5f}  species {best_p['species']}", flush=True)

    deadline = time.time() + args.minutes * 60
    cur_p, cur = copy.deepcopy(best_p), best
    trials = improved = 0
    while time.time() < deadline:
        q = perturb(cur_p, rng)
        try:
            a, s = balanced_plan(level, q)
        except Exception as e:
            continue
        sc = s.score()["final"]; trials += 1
        if sc > cur:
            cur_p, cur = q, sc
            if sc > best:
                best, best_p, best_acts, best_sim = sc, copy.deepcopy(q), a, s
                improved += 1
                print(f"  +{improved:>3}  trial {trials:>4}  {best:.5f}  "
                      f"fill {s.score()['C']}  {s.score()['counts']}", flush=True)
        elif trials % 60 == 0 and rng.random() < 0.5:
            cur_p, cur = copy.deepcopy(best_p), best       # return to the best

    print(f"\nL{n} done: {trials} trials, best {best:.5f}")
    problems = validate(best_acts, level)
    print("validate:", problems or "clean")
    save_candidate(n, "hillclimb", best_acts, best_sim, best_p)
    Path("out/submissions").mkdir(exist_ok=True, parents=True)
    Path(f"out/submissions/LEVEL{n}_hillclimb.json").write_text(
        json.dumps(to_submission(best_acts)))
    json.dump(best_p, open(OUT / f"LEVEL{n}_hillclimb_params.json", "w"), indent=1)
    print(f"wrote out/submissions/LEVEL{n}_hillclimb.json")


if __name__ == "__main__":
    main()
