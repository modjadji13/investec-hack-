"""Calibrate engine rules against real judge logs.

The judge prints final per-species counts. That's ground truth. For each rule
combination, replay every submission we have a log for and measure how far the
engine's final counts are from the judge's. Lowest error wins.

    python3 calibrate.py                      # all variants, all runs
    python3 calibrate.py --levels 1 2         # quick: small levels only
"""
import argparse, glob, itertools, json, re, sys, time
from pathlib import Path

from photospheria import load_level, submission
from photospheria import engine
from photospheria.catalogue import BY_INDEX, BY_NAME
from photospheria.engine import Simulator
from photospheria.strategies import level_copy

LOG_DIR = "/root/.claude/uploads/e181bcfb-1389-55bb-af48-b64b20b2982d"
OPT = "/tmp/claude-0/opt/photospheria/out/submissions"
OUTS = "/mnt/user-data/outputs"

# judge score -> (level number, submission file)
RUNS = {
    222_745_174: (1, f"{OUTS}/LEVEL1_submission.json"),
    284_416_228: (2, f"{OUTS}/LEVEL2_ROLLBACK_284M.json"),
    187_985_678: (2, f"{OPT}/LEVEL2_optimized.json"),
    208_970_159: (3, f"{OUTS}/LEVEL3_ROLLBACK_209M.json"),
    153_208_357: (3, f"{OPT}/LEVEL3_optimized.json"),
    204_979_123: (4, f"{OUTS}/LEVEL4_submission.json"),
    260_868_897: (4, f"{OPT}/LEVEL4_optimized.json"),
}


def judge_counts():
    """Parse every log once; return {score: {species: count}} plus the stats."""
    out = {}
    for f in glob.glob(f"{LOG_DIR}/*evaluation*.log"):
        txt = open(f).read()
        m = re.search(r"Setting score to (\d+)", txt)
        if not m:
            continue
        score = int(m.group(1))
        arr = re.search(r"'plant_counts': array\(\[(.*?)\]\)", txt, re.S).group(1)
        nums = [float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", arr)]
        counts = {BY_INDEX[i + 1]["plant"]: int(round(n)) for i, n in enumerate(nums) if n > 0}
        stats = {k: float(re.search(rf"'{k}': (?:np\.int64\()?([\d.]+)", txt).group(1))
                 for k in ("main_score", "longevity_score", "entropy",
                           "total_plants_planted_C", "density_factor")}
        out[score] = (counts, stats)
    return out


def replay(level_n, path):
    lvl = load_level(f"data/level{level_n}.json")
    acts = submission.from_submission(json.load(open(path)))
    sim = Simulator(level_copy(lvl)).run(acts)
    s = sim.score()
    return s, sim.rejected


def error(mine, theirs):
    """Mean absolute error in species counts, as a fraction of the judge's total."""
    keys = set(mine) | set(theirs)
    total = max(1, sum(theirs.values()))
    return sum(abs(mine.get(k, 0) - theirs.get(k, 0)) for k in keys) / total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", nargs="+", type=int, default=[1, 2, 3, 4])
    args = ap.parse_args()

    truth = judge_counts()
    runs = {sc: v for sc, v in RUNS.items() if v[0] in args.levels and sc in truth}
    variants = [("same", "rank", "age_mod", False), ("same", "rank_always", "age_mod", True)]

    print(f"{len(runs)} judge runs, {len(variants)} rule variants\n")
    results = {}
    for overwrite, compete, clock, needmat in variants:
        engine.MANUAL_OVERWRITE, engine.SPREAD_COMPETE = overwrite, compete
        engine.SPREAD_CLOCK, engine.SPREAD_NEEDS_MATURITY = clock, needmat
        errs = []
        print(f"=== overwrite={overwrite:<5} compete={compete:<9} clock={clock:<10} needs_maturity={needmat}")
        for sc, (n, path) in sorted(runs.items(), key=lambda x: x[1][0]):
            jc, jst = truth[sc]
            t0 = time.time()
            s, rej = replay(n, path)
            e = error(s["counts"], jc)
            errs.append(e)
            top = ", ".join(f"{k.split()[0][:5]} {s['counts'].get(k,0)}/{jc.get(k,0)}"
                            for k in sorted(jc, key=lambda k: -jc[k])[:5])
            print(f"  L{n} {sc:>12,}  err {e:.3f}  C {s['C']}/{int(jst['total_plants_planted_C'])}"
                  f"  H {s['H']:.3f}/{jst['entropy']:.3f}  rej {rej}  [{top}]  {time.time()-t0:.0f}s")
        results[(overwrite, compete, clock, needmat)] = sum(errs) / len(errs)
        print(f"  mean error {results[(overwrite, compete, clock, needmat)]:.3f}\n")

    best = min(results, key=results.get)
    print("RANKING (lower is better):")
    for k, v in sorted(results.items(), key=lambda x: x[1]):
        print(f"  {v:.3f}  overwrite={k[0]:<5} compete={k[1]:<9} clock={k[2]:<10} needs_maturity={k[3]}")
    print(f"\nBEST: {best}")


if __name__ == "__main__":
    main()
