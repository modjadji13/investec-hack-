import json
import re
import time
from pathlib import Path
import numpy as np
from photospheria import load_level
from photospheria.catalogue import BY_NAME
from photospheria.fast_eval import FastSimulator
from photospheria.submission import from_submission

output = Path('out/optimization')
output.mkdir(parents=True, exist_ok=True)
results = {}
for n in range(1,5):
    level = load_level(f'data/level{n}.json')
    actions = from_submission(json.loads(Path(f'data/level{n}_submission.json').read_text()))
    start = time.perf_counter()
    sim = FastSimulator(level).run(actions)
    score = sim.score()
    source = Path(f'out/level{n}_replay.html').read_text(encoding='utf-8-sig')
    frames = json.loads(re.search(r'const F=(.*?), P=',source,re.S)[1])
    final = frames[-1]
    expected = np.array([BY_NAME[s]['index'] if s in BY_NAME else 0
                         for row in final['grid'] for s in row])
    assert np.array_equal(expected,sim.sp), (n, int(np.sum(expected!=sim.sp)))
    assert abs(final['score']['final']-score['final']) < 1e-12, (n, final['score'],score)
    results[n] = {**score, 'seconds':time.perf_counter()-start}
    print(n, json.dumps(results[n]), flush=True)
    np.savez_compressed(output/f'baseline-{n}.npz',sp=sim.sp,age=sim.age,nut=sim.nut)
(output/'baselines.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('All four final grids and scores match the original simulator exactly.',flush=True)
