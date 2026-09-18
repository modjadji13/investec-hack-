import json
import random
from pathlib import Path
import numpy as np
from photospheria import load_level
from photospheria.catalogue import BY_NAME, BY_INDEX
from photospheria.fast_eval import FastSimulator, can
from photospheria.submission import from_submission
from optimize_levels import OUT, save_candidate


def augment(level, original, last, include_razor=False, direction=0):
    sim=FastSimulator(level)
    actions={}
    eligible=['Grass','Rose Bush','Lavender','Dwarf Sunflower','Oak Tree',
              'Orange Blossom','Ironthorn Shrub','Crimson Vine','Glowcap Fungus',
              'Crystal Cactus','Purple Canopy Tree','Silver Fern']
    if include_razor:eligible.append('Razorgrass')
    for t in range(level.ticks):
        acts=list(original.get(t,()))
        if t>=level.ticks-last:
            acts=[]
            counts=sim.counts()
            active=[s for s in eligible if s in sim.unlocked]
            tally={s:counts.get(s,0) for s in active}
            used=set()
            for j in range(20):
                target=min(active,key=lambda s:tally[s])
                donors=sorted(counts,key=lambda s:counts[s],reverse=True)
                done=False
                for donor in donors:
                    if counts[donor]<=tally[target] or donor==target:continue
                    positions=np.flatnonzero(sim.sp==BY_NAME[donor]['index'])
                    if direction==1:positions=positions[::-1]
                    elif direction==2:positions=positions[np.argsort(positions%level.width,kind='stable')]
                    for pos in positions:
                        pos=int(pos)
                        if pos not in used and sim.can_occupy(target,pos//level.width,pos%level.width):
                            acts.append((BY_NAME[target]['index'],pos//level.width,pos%level.width))
                            used.add(pos);tally[target]+=1;counts[donor]-=1
                            if donor in tally:tally[donor]-=1
                            done=True;break
                    if done:break
                if not done:
                    active.remove(target)
                    if not active:break
        if acts:actions[t]=acts
        sim.step(acts)
    return actions,sim


if __name__=='__main__':
    n=2
    level=load_level(f'data/level{n}.json')
    original=from_submission(json.loads((OUT/f'LEVEL{n}_candidate.json').read_text()))
    best=json.loads((OUT/f'LEVEL{n}_candidate_metrics.json').read_text())['final']
    for last in [5,10,15,20,30,40,50,60]:
        for direction in [0,1,2]:
            acts,sim=augment(level,original,last,False,direction)
            s=sim.score()
            print('augment',last,direction,round(s['final'],5),s['counts'],flush=True)
            if s['final']>best:
                best=s['final']
                save_candidate(n,'candidate',acts,sim,{'augmentation':last,'direction':direction})
                print('NEW BEST',best,flush=True)
