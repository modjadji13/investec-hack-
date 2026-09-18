"""Watch the simulation. Terminal renderer with ANSI colour, plus an HTML replay."""
from __future__ import annotations

import json
import html
import shutil
import sys
import time
from pathlib import Path

from .catalogue import BY_NAME
from .engine import Simulator

RESET = "\033[0m"
# 256-colour codes, one per species, chosen to stay distinct on both terminal themes
COLOURS = {
    "Grass": 34, "Rose Bush": 167, "Lavender": 98, "Dwarf Sunflower": 178,
    "Oak Tree": 36, "Blue Moss": 68, "Crimson Vine": 125, "Silver Fern": 108,
    "Glowcap Fungus": 143, "Purple Canopy Tree": 92, "Stone Reed": 101,
}
GLYPHS = {
    "Grass": "g", "Rose Bush": "R", "Lavender": "L", "Dwarf Sunflower": "S",
    "Oak Tree": "O", "Blue Moss": "m", "Crimson Vine": "v", "Silver Fern": "f",
    "Glowcap Fungus": "c", "Purple Canopy Tree": "P", "Stone Reed": "r",
}


def glyph(species: str) -> str:
    return GLYPHS.get(species, species[0].lower())


def paint(sim: Simulator, colour=True) -> str:
    out = []
    for r in range(sim.L.height):
        line = []
        for c in range(sim.L.width):
            cell = sim.g[r][c]
            terr = sim.L.terrain[r][c]
            if cell.species:
                ch = glyph(cell.species)
                if colour:
                    code = COLOURS.get(cell.species, 245)
                    ch = f"\033[38;5;{code}m{ch}{RESET}"
                line.append(ch)
            elif terr == "path":
                line.append("\033[38;5;240m:\033[0m" if colour else ":")
            elif terr == "void":
                line.append(" ")
            elif cell.dead_matter:
                line.append("\033[38;5;95m.\033[0m" if colour else ".")
            else:
                line.append("\033[38;5;238m·\033[0m" if colour else "·")
        out.append("".join(line))
    return "\n".join(out)


def status(sim: Simulator) -> str:
    s = sim.score()
    return (f"tick {sim.tick:>4}/{sim.L.ticks}   season {sim.season:<7} "
            f"species {s['species']:>2}   filled {s['C']:>5}/{s['Cmax']} "
            f"({s['size']:>5.1%})   H {s['H']:.4f}   score {s['final']:.4f}")


def watch(sim: Simulator, actions: dict, fps: float = 12.0, every: int = 1,
          colour: bool = True):
    """Play the simulation in the terminal. Ctrl-C to stop early."""
    hide, show = "\033[?25l", "\033[?25h"
    first = min(actions) if actions else 0
    sys.stdout.write(hide)
    try:
        for t in range(sim.L.ticks):
            sim.step(actions.get(t, []))
            # Fast-forward the dead stretch before the first planting instead of
            # animating hundreds of frames of empty ground.
            if t < first - 1:
                if t % 50 == 0:
                    sys.stdout.write(f"\rfast-forwarding to tick {first} "
                                     f"(nothing is planted before then)… {t}")
                    sys.stdout.flush()
                continue
            if t % every and t != sim.L.ticks - 1:
                continue
            sys.stdout.write("\033[H\033[J")
            sys.stdout.write(paint(sim, colour) + "\n\n" + status(sim) + "\n")
            sys.stdout.flush()
            time.sleep(1.0 / fps)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(show)
    return sim


def snapshot(sim: Simulator) -> dict:
    grid = []
    for r in range(sim.L.height):
        grid.append([sim.g[r][c].species or
                     ("#" if sim.L.terrain[r][c] == "path" else
                      "%" if sim.L.terrain[r][c] == "stone" else
                      "!" if sim.L.terrain[r][c] == "crack" else
                      "" if sim.L.terrain[r][c] == "soil" else " ")
                     for c in range(sim.L.width)])
    return {"tick": sim.tick, "grid": grid, "score": sim.score()}


# Validated categorical palette - these six clear the all-pairs colourblind
# separation floor together. Letters in each cell carry the identity too.
PALETTE = {
    "Grass": "#3fa93f", "Rose Bush": "#e66767", "Lavender": "#9085e9",
    "Dwarf Sunflower": "#e2a636", "Oak Tree": "#2fbd8d", "Blue Moss": "#3987e5",
    "Crimson Vine": "#d55181", "Silver Fern": "#9fb96a", "Glowcap Fungus": "#c9b458",
    "Purple Canopy Tree": "#7b5fd4", "Stone Reed": "#a0a48c",
}


def write_html_replay(sim: Simulator, actions: dict, path="out/replay.html",
                      every: int = 10, max_frames: int = 260,
                      title="Photospheria replay"):
    """Run the sim and write a scrubbable HTML replay.

    Frames are captured ADAPTIVELY. On Level 1 nothing is planted until tick
    473, so a fixed interval spends 90% of the replay on an empty grid. We keep
    a frame whenever the grid actually changed, plus a sparse baseline so the
    idle stretch is still represented rather than cut out and confusing.
    """
    frames, last_sig, since = [], None, 0
    for t in range(sim.L.ticks):
        sim.step(actions.get(t, []))
        sig = tuple(tuple(row) for row in
                    ((cell.species for cell in r) for r in sim.g))
        changed = sig != last_sig
        since += 1
        # an empty grid needs only an occasional keyframe; a changing one needs all
        floor = every * 10 if not any(any(r) for r in sig) else every
        if changed or since >= floor or t == sim.L.ticks - 1:
            frames.append(snapshot(sim))
            last_sig, since = sig, 0

    if len(frames) > max_frames:                       # thin the idle stretch first
        keep, step = [], len(frames) / max_frames
        for i in range(max_frames):
            keep.append(frames[min(len(frames) - 1, int(i * step))])
        keep[-1] = frames[-1]
        frames = keep

    first_planted = next((i for i, f in enumerate(frames) if f["score"]["C"]), 0)
    used = sorted({sp for f in frames for row in f["grid"] for sp in row
                   if sp not in ("", "#", "%", "!", " ")})
    legend = [{"name": n, "colour": PALETTE.get(n, "#8a8a8a")} for n in used]

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_HTML
                 .replace("__FRAMES__", json.dumps(frames))
                 .replace("__PALETTE__", json.dumps(PALETTE))
                 .replace("__LEGEND__", json.dumps(legend))
                 .replace("__START__", str(first_planted))
                 .replace("__TITLE__", html.escape(title))
                 .replace("__FIRST__", json.dumps(min((t for t, a in actions.items()
                                                       if a), default=None))))
    return path, len(frames)


_HTML = """<!doctype html><meta charset=utf-8><meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title>
<style>
 :root{--bg:#0f1411;--panel:#161e19;--line:#2b3a32;--ink:#e6ede8;--dim:#93a89c;
       --empty:#27332c;--path:#1a231e}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);
      font:14px/1.5 system-ui,-apple-system,sans-serif;padding:20px 16px 40px}
 .wrap{max-width:900px;margin:0 auto;display:flex;flex-direction:column;gap:16px}
 h1{font-size:1.1rem;margin:0;font-weight:600;letter-spacing:.01em}
 .stage{display:grid;grid-template-columns:minmax(0,1fr) 190px;gap:16px;align-items:start}
 @media(max-width:640px){.stage{grid-template-columns:1fr}}
 canvas{image-rendering:pixelated;border:1px solid var(--line);width:100%;
        height:auto;display:block;background:var(--bg)}
 .side{display:flex;flex-direction:column;gap:14px}
 .card{background:var(--panel);border:1px solid var(--line);padding:12px;
       display:flex;flex-direction:column;gap:8px}
 .k{font:11px ui-monospace,monospace;letter-spacing:.09em;text-transform:uppercase;
    color:var(--dim)}
 .rows{display:flex;flex-direction:column;gap:5px}
 .row{display:grid;grid-template-columns:14px 1fr auto;gap:8px;align-items:center;
      font:12px ui-monospace,monospace;font-variant-numeric:tabular-nums}
 .sw{width:14px;height:14px;border-radius:2px}
 .met{display:flex;justify-content:space-between;font:12px ui-monospace,monospace;
      font-variant-numeric:tabular-nums}
 .met b{font-weight:600}
 .bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
 button{font:13px system-ui;padding:6px 14px;background:#1f2b24;color:var(--ink);
        border:1px solid var(--line);border-radius:3px;cursor:pointer}
 button:hover{border-color:#4d7d68}
 input[type=range]{flex:1;min-width:180px;accent-color:#3fa93f}
 .note{color:var(--dim);font-size:12px}
</style>
<div class=wrap>
 <h1>__TITLE__</h1>
 <div class=stage>
  <div>
   <canvas id=cv width=600 height=600></canvas>
   <div class=bar style="margin-top:12px">
     <button id=play>Play</button>
     <input type=range id=sl min=0 value=0 aria-label="Replay frame">
   </div>
   <p class=note id=note></p>
  </div>
  <div class=side>
   <div class=card>
     <span class=k>Score</span>
     <div class=met><span>tick</span><b id=mT>0</b></div>
     <div class=met><span>species</span><b id=mS>0</b></div>
     <div class=met><span>filled</span><b id=mC>0</b></div>
     <div class=met><span>diversity H</span><b id=mH>0</b></div>
     <div class=met><span>final</span><b id=mF>0</b></div>
   </div>
   <div class=card>
     <span class=k>Species</span>
     <div class=rows id=leg></div>
   </div>
   <div class=card>
     <span class=k>Terrain</span>
     <div class=rows>
       <div class=row><span class=sw style="background:#27332c"></span><span>plantable</span><span></span></div>
       <div class=row><span class=sw style="background:#1a231e"></span><span>path</span><span></span></div>
       <div class=row><span class=sw style="background:#45505a"></span><span>stone</span><span></span></div>
       <div class=row><span class=sw style="background:#593d32"></span><span>crack</span><span></span></div>
       <div class=row><span class=sw style="background:#0f1411;border:1px solid #2b3a32"></span><span>outside</span><span></span></div>
     </div>
   </div>
  </div>
 </div>
</div>
<script>
const F=__FRAMES__, P=__PALETTE__, LEG=__LEGEND__, START=__START__, FIRST=__FIRST__;
const cv=document.getElementById('cv'), x=cv.getContext('2d');
const sl=document.getElementById('sl'), note=document.getElementById('note');
const play=document.getElementById('play');
const [mT,mS,mC,mH,mF]=['mT','mS','mC','mH','mF'].map(id=>document.getElementById(id));
cv.width=F[0].grid[0].length*4; cv.height=F[0].grid.length*4;
sl.max=F.length-1; sl.value=START;

document.getElementById('leg').innerHTML = LEG.map(l =>
 `<div class=row><span class=sw style="background:${l.colour}"></span>`+
 `<span>${l.name}</span><span id="cnt-${l.name.replace(/ /g,'_')}">0</span></div>`).join('');

function draw(i){
  const f=F[i], g=f.grid, n=g.length, px=cv.width/g[0].length;
  x.fillStyle='#0f1411'; x.fillRect(0,0,cv.width,cv.height);
  const tally={};
  for(let r=0;r<n;r++) for(let c=0;c<g[r].length;c++){
    const v=g[r][c];
    if(v===' ') continue;
    x.fillStyle = v==='#' ? '#1a231e' : v==='%' ? '#45505a' :
      v==='!' ? '#593d32' : v==='' ? '#27332c' : (P[v]||'#8a8a8a');
    x.fillRect(c*px,r*px,px+0.6,px+0.6);
    if(v && !['#','%','!'].includes(v)) tally[v]=(tally[v]||0)+1;
  }
  const s=f.score;
  mT.textContent=f.tick; mS.textContent=s.species;
  mC.textContent=s.C+'/'+s.Cmax;
  mH.textContent=s.H.toFixed(4); mF.textContent=s.final.toFixed(4);
  LEG.forEach(l=>{
    const el=document.getElementById('cnt-'+l.name.replace(/ /g,'_'));
    if(el) el.textContent = tally[l.name]||0;
  });
  note.textContent = s.C ? '' : FIRST === null ? 'No planting actions in this run.' :
    f.tick <= FIRST ? `Nothing planted yet. Planting begins at tick ${FIRST}. Idle time is compressed.` :
    'No living plants at this tick.';
}
sl.oninput=()=>draw(+sl.value);
let timer=null;
play.onclick=e=>{
  if(timer){clearInterval(timer);timer=null;e.target.textContent='Play';return;}
  e.target.textContent='Pause';
  if(+sl.value>=F.length-1) sl.value=START;
  timer=setInterval(()=>{
    if(+sl.value>=F.length-1){clearInterval(timer);timer=null;play.textContent='Play';return;}
    sl.value=+sl.value+1; draw(+sl.value);
  },90);
};
draw(START);
</script>"""
