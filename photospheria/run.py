#!/usr/bin/env python3
"""Command line for the Photospheria simulator.

    python run.py info                 what the level file actually contains
    python run.py tree                 which species are reachable, and how
    python run.py watch                play a run in the terminal
    python run.py watch --naive        play the bad baseline, to see it fail
    python run.py solve                tune a strategy and write out/submission.json
    python run.py replay               write out/replay.html to open in a browser
    python run.py check out/submission.json     re-score a submission file

Add --level data/level1.json to point at a different level.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from photospheria import load_level, render, strategies, submission
from photospheria.catalogue import BY_NAME, PLANTS, STARTERS
from photospheria.engine import CELL_NUTRIENTS, MAX_PER_TICK, Simulator
from photospheria.level import DEFAULT_TERRAIN, TERRAIN_MAP


def cmd_info(args):
    lvl = load_level(args.level)
    print(f"grid          {lvl.width} x {lvl.height}  ({lvl.cells_total} cells, "
          f"Cmax for scoring)")
    print(f"ticks         {lvl.ticks}")
    print(f"animals       {'enabled' if lvl.animals_enabled else 'DISABLED'}")
    print(f"seasons       {dict(sorted(lvl.seasons.items()))}")
    print(f"events        {dict(sorted(lvl.events.items())) or 'none'}")
    print(f"defined cells {len(lvl.defined)}  "
          f"({lvl.cells_total - len(lvl.defined)} undefined -> '{DEFAULT_TERRAIN}')")

    inv = {}
    for _, _, t, s in lvl.defined:
        inv[(t, s)] = inv.get((t, s), 0) + 1
    print("\ncell inventory (terrain, soil) -> count")
    soil_name = {0: "Dirt", 1: "Mud", 2: "Clay", 3: "Burnt"}
    for k in sorted(inv):
        print(f"   terrain {k[0]} ({TERRAIN_MAP.get(k[0], 'void'):<4}) "
              f"soil {k[1]} ({soil_name[k[1]]:<5}) -> {inv[k]:>5}")

    cells = strategies.plantable_cells(lvl)
    beds = lvl.beds(cells)
    print(f"\nplantable by the starting five: {len(cells)} cells in {len(beds)} beds "
          f"(sizes {[len(b) for b in beds]})")
    print(f"max fill C/Cmax = {len(cells)}/{lvl.cells_total} = "
          f"{len(cells) / lvl.cells_total:.1%}")
    safe = strategies.safe_planting_tick(lvl)
    budget = (lvl.ticks - safe) * MAX_PER_TICK
    print(f"\na cell dies {int(CELL_NUTRIENTS)} ticks after planting, so only ticks "
          f"{safe}..{lvl.ticks - 1} survive to scoring")
    print(f"that is {budget} placements for {len(cells)} cells "
          f"({budget / max(len(cells), 1):.1f}x more than you need)")

    print("\nmap:")
    sim = Simulator(strategies.level_copy(lvl))
    print(render.paint(sim, colour=not args.no_colour))


def cmd_tree(args):
    lvl = load_level(args.level)
    have = set(STARTERS)
    animals_ok = lvl.animals_enabled
    events_ok = set(lvl.events.values())
    print(f"start with: {', '.join(STARTERS)}")
    print(f"animals {'enabled' if animals_ok else 'DISABLED'}; "
          f"events that fire: {sorted(events_ok) or 'none'}\n")
    from photospheria.catalogue import ANIMAL_BY_NAME, UNLOCK_BY_NAME

    def reachable(node):
        if "op" in node:
            if node["op"] == "AND":
                return all(reachable(c) for c in node["children"])
            if node["op"] == "OR":
                return any(reachable(c) for c in node["children"])
            return True
        t = node["type"]
        if t == "species_absent":
            return True
        if t == "species_present":
            s = node["species"]
            if s in ANIMAL_BY_NAME:
                return animals_ok
            return s in have
        if t in ("coverage", "count"):
            return node["plant"] in have
        if t == "event":
            return node["event"] in events_ok
        return True

    wave = 1
    while True:
        newly = [p["plant"] for p in PLANTS if p["plant"] not in have
                 and (p["plant"] not in UNLOCK_BY_NAME or reachable(UNLOCK_BY_NAME[p["plant"]]))]
        if not newly:
            break
        print(f"wave {wave}: {', '.join(sorted(newly))}")
        have |= set(newly)
        wave += 1

    blocked = [p["plant"] for p in PLANTS if p["plant"] not in have]
    import math
    print(f"\nREACHABLE: {len(have)}/{len(PLANTS)}")
    print(f"max diversity H with {len(have)} species evenly spread = "
          f"{math.log(len(have)) / math.log(len(PLANTS)):.4f}")
    if blocked:
        print(f"BLOCKED ({len(blocked)}): {', '.join(sorted(blocked))}")


def _build(args, lvl):
    if args.naive:
        return strategies.naive_even(lvl)
    if args.quick:
        return strategies.late_blocks(lvl)
    actions, score, weights = strategies.tune(lvl, rounds=args.rounds,
                                              verbose=not args.quiet)
    return actions


def cmd_watch(args):
    lvl = load_level(args.level)
    actions = _build(args, lvl)
    sim = Simulator(strategies.level_copy(lvl))
    render.watch(sim, actions, fps=args.fps, every=args.every,
                 colour=not args.no_colour)
    s = sim.score()
    print(f"\nfinal: {s['final']:.4f}   H {s['H']:.4f}   "
          f"filled {s['C']}/{s['Cmax']}   species {s['species']}")
    for name, n in s["counts"].items():
        print(f"   {name:<20} {n:>5}  ({n / s['C']:.1%})")


def cmd_solve(args):
    lvl = load_level(args.level)
    actions = _build(args, lvl)
    sim = Simulator(strategies.level_copy(lvl)).run(actions)
    s = sim.score()
    problems = submission.validate(actions, lvl)
    print("\n" + submission.summarise(actions))
    print(f"\npredicted score {s['final']:.4f}   H {s['H']:.4f}   "
          f"fill {s['size']:.1%}   species {s['species']}")
    for name, n in s["counts"].items():
        print(f"   {name:<20} {n:>5}  ({n / s['C']:.1%})")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("   " + p)
    else:
        print("\nvalidates clean: every tick in range, <=20 plants, all in bounds")
    path = submission.save(actions, args.out)
    print(f"wrote {path}")


def cmd_replay(args):
    lvl = load_level(args.level)
    actions = _build(args, lvl)
    sim = Simulator(strategies.level_copy(lvl))
    path, n = render.write_html_replay(
        sim, actions, args.out_html, every=args.every, max_frames=args.max_frames,
        title=Path(args.level).stem.upper() + " replay")
    print(f"wrote {path} ({n} frames) - open it in a browser")


def cmd_all(args):
    """Build one dashboard containing independent replays for Levels 1–4."""
    panels = []
    for number in range(1, 5):
        level_path = Path(args.data_dir) / f"level{number}.json"
        submission_path = Path(args.data_dir) / f"level{number}_submission.json"
        lvl = load_level(level_path)
        with open(submission_path, encoding="utf-8-sig") as fh:
            actions = submission.from_submission(json.load(fh))
        problems = submission.validate(actions, lvl)
        if problems:
            raise ValueError(f"Invalid Level {number} submission: " + "; ".join(problems))
        sim = Simulator(strategies.level_copy(lvl))
        replay_name = f"level{number}_replay.html"
        replay_path = Path(args.out_html).parent / replay_name
        path, frame_count = render.write_html_replay(
            sim, actions, replay_path, every=args.every,
            max_frames=args.max_frames,
            title=f"L{number} | {lvl.width} x {lvl.height} | {lvl.ticks} ticks")
        score = sim.score()
        print(f"L{number}: {frame_count} frames, score {score['final']:.4f}, "
              f"filled {score['C']}/{score['Cmax']}, rejected {sim.rejected}")
        panels.append(f'<iframe title="Level {number}" src="{Path(path).name}"></iframe>')

    output = Path(args.out_html)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Photospheria | Levels 1-4</title><style>
*{box-sizing:border-box}html,body{height:100%;margin:0;background:#0b100d;color:#e6ede8;
font:14px/1.4 system-ui,-apple-system,sans-serif;overflow:hidden}
header{height:52px;padding:9px 18px;border-bottom:1px solid #2b3a32;display:flex;
align-items:baseline;gap:14px}h1{font-size:17px;margin:0}header span{color:#93a89c;font-size:12px}
main{height:calc(100% - 52px);display:grid;grid-template-columns:1fr 1fr;
grid-template-rows:1fr 1fr;gap:1px;background:#2b3a32}
iframe{width:100%;height:100%;border:0;background:#0f1411}
@media(max-width:760px){html,body{overflow:auto}main{height:auto;grid-template-columns:1fr;
grid-template-rows:none}iframe{height:650px}}
</style><header><h1>Photospheria | L1, L2, L3, L4</h1>
<span>Each plane has independent playback and scoring.</span></header><main>'''
                      + ''.join(panels) + '</main></html>', encoding="utf-8")
    print(f"wrote {output} - open it in a browser")


def cmd_check(args):
    lvl = load_level(args.level)
    with open(args.file) as fh:
        actions = submission.from_submission(json.load(fh))
    problems = submission.validate(actions, lvl)
    sim = Simulator(strategies.level_copy(lvl)).run(actions)
    s = sim.score()
    print(submission.summarise(actions))
    print(f"\npredicted score {s['final']:.4f}   H {s['H']:.4f}   "
          f"fill {s['size']:.1%}   species {s['species']}   "
          f"rejected placements {sim.rejected}")
    for p in problems:
        print("   PROBLEM: " + p)


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--level", default="data/level1.json")
    common.add_argument("--naive", action="store_true",
                        help="use the bad baseline strategy, to watch it fail")
    common.add_argument("--quick", action="store_true", help="skip tuning, one pass")
    common.add_argument("--rounds", type=int, default=9)
    common.add_argument("--quiet", action="store_true")
    common.add_argument("--no-colour", action="store_true")
    common.add_argument("--fps", type=float, default=12.0)
    common.add_argument("--every", type=int, default=5, help="render every Nth tick")
    common.add_argument("--out", default="out/submission.json")
    common.add_argument("--out-html", default="out/replay.html")
    common.add_argument("--max-frames", type=int, default=80,
                        help="maximum frames stored per replay")

    ap = argparse.ArgumentParser(description=__doc__, parents=[common],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in [("info", cmd_info), ("tree", cmd_tree), ("watch", cmd_watch),
                     ("solve", cmd_solve), ("replay", cmd_replay)]:
        sub.add_parser(name, parents=[common]).set_defaults(fn=fn)
    c = sub.add_parser("check", parents=[common])
    c.add_argument("file")
    c.set_defaults(fn=cmd_check)
    all_levels = sub.add_parser("all", parents=[common],
                                help="show Levels 1–4 on one screen")
    all_levels.add_argument("--data-dir", default="data")
    all_levels.set_defaults(fn=cmd_all, out_html="out/all-levels.html")

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
