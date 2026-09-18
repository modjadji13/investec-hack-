import argparse
import copy
import json
import math
import random
import time
from pathlib import Path
from optimize_levels import balanced_plan, save_candidate, OUT
from photospheria import load_level

ap=argparse.ArgumentParser()
ap.add_argument('--rounds',type=int,default=80)
ap.add_argument('--levels',type=int,nargs='+',default=[2,3,4])
args=ap.parse_args()
for n in args.levels:
    level=load_level(f'data/level{n}.json')
    record=json.loads((OUT/f'LEVEL{n}_candidate_metrics.json').read_text())
    best=record['final'];params=record['params']
    rng=random.Random(801+n)
    for trial in range(args.rounds):
        p=copy.deepcopy(params)
        names=p['species']
        mode=trial%8
        if mode==0:
            i=rng.randrange(len(names)); p['weights'][i]*=rng.choice([.65,.8,1.2,1.4])
        elif mode==1:
            s=rng.choice(names)
            p['strides'][s]=rng.choice([20,30,40,50,60]) if s=='Crimson Vine' else rng.choice([10,14,18,22]) if s=='Rose Bush' else rng.choice([4,5,6,7,8,9,11,13])
        elif mode==2:
            counts=record['counts'];total=sum(counts.values())
            p['weights']=[weight*(total/len(names)/max(100,counts.get(s,0)))**.35 for weight,s in zip(p['weights'],names)]
        elif mode==3:
            a,b=rng.sample(range(len(names)),2)
            names[a],names[b]=names[b],names[a]
        elif mode==4:
            s=rng.choice(names)
            p.setdefault('delays',{})[s]=rng.choice([0,0,5,10,15,20,30])
        elif mode==5:
            p['window']=rng.choice([90,95,99]);p['topup']=rng.choice([20,35,50,65,80]);p['seed']=rng.randrange(1000)
        elif mode==6:
            p['vertical']=not p['vertical']
        else:
            p['weights']=[w*rng.uniform(.8,1.2) for w in p['weights']]
            p['reverse']=not p.get('reverse',False)
        acts,sim=balanced_plan(level,p)
        s=sim.score()
        if s['final']>best:
            best=s['final'];params=p
            record=save_candidate(n,'candidate',acts,sim,p)
            print('BEST',n,trial,round(best,6),s['C'],s['counts'],flush=True)
        elif trial%10==0:
            print('progress',n,trial,'best',round(best,6),flush=True)
    print('FINISHED',n,best,flush=True)
