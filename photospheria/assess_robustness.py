import json
from pathlib import Path
from photospheria import load_level
from photospheria.fast_eval import FastSimulator
from photospheria.submission import from_submission
from optimize_levels import robust_metrics

out=Path('out/optimization')
report={}
for n in range(1,5):
    report[n]={}
    for variant,dead,competition in [('legacy',False,False),('dead_matter',True,False),
                                      ('mature_competition',True,True)]:
        scores={}
        for tag in ('original','candidate'):
            a=from_submission(json.loads((out/f'LEVEL{n}_{tag}.json').read_text()))
            sim=FastSimulator(load_level(f'data/level{n}.json'),retain_dead=dead,
                              mature_competition=competition).run(a)
            scores[tag]={'score':sim.score(),'sensitivity':robust_metrics(sim)}
        ratios={k:(v/scores['original']['sensitivity'][k]-1) for k,v in scores['candidate']['sensitivity'].items()}
        report[n][variant]={'scores':scores,'relative_gain_by_exponents':ratios}
        print(n,variant,'baseline',round(scores['original']['score']['final'],5),
              'candidate',round(scores['candidate']['score']['final'],5),
              'gain range',round(min(ratios.values())*100,1),round(max(ratios.values())*100,1),flush=True)
(out/'robustness.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
