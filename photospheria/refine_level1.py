import json
import random
from pathlib import Path
from photospheria import load_level
from photospheria.catalogue import STARTERS
from photospheria.fast_eval import FastSimulator
from photospheria.strategies import late_blocks
from optimize_levels import read_actions, save_candidate, robust_metrics

level=load_level('data/level1.json')
original=read_actions(1)
base=FastSimulator(level).run(original)
save_candidate(1,'original',original,base)
save_candidate(1,'candidate',original,base,{'strategy':'original'})
best=base.score()['final']
base_metrics=robust_metrics(base)
rng=random.Random(19)
print('BASE',best,base.score(),flush=True)
for trial in range(50):
    order=list(STARTERS);rng.shuffle(order)
    weights=[1.]*5
    for step in range(10):
        actions=late_blocks(level,weights=weights,order=order)
        sim=FastSimulator(level).run(actions)
        s=sim.score()
        if s['final']>best and all(v>=base_metrics[k]-1e-12 for k,v in robust_metrics(sim).items()):
            best=s['final']
            save_candidate(1,'candidate',actions,sim,{'weights':weights,'order':order})
            print('BEST',trial,step,best,s['counts'],s['longevity'],flush=True)
        target=1980/5
        weights=[w*(target/max(1,s['counts'].get(sp,0)))**.5 for w,sp in zip(weights,STARTERS)]
    if trial%10==0:print('progress',trial,'best',best,flush=True)
print('FINISHED',best,flush=True)
