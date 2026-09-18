"""Search planting plans against the checked fast local replica.

Outputs are candidates for the judge, not claims about its unknown exponents.
"""
import argparse
import json
import math
import random
import time
from pathlib import Path
import numpy as np
from photospheria import load_level
from photospheria.catalogue import BY_NAME, BY_INDEX, STARTERS
from photospheria.fast_eval import FastSimulator, can
from photospheria.submission import from_submission, to_submission, validate

OUT = Path('out/optimization')


def read_actions(n):
    return from_submission(json.loads(Path(f'data/level{n}_submission.json').read_text()))


def balanced_plan(level, params, retain_dead=False):
    """Independent territories with staged seeding when each species unlocks."""
    sim = FastSimulator(level, retain_dead=retain_dead)
    h, w, end = level.height,level.width,level.ticks
    species = params['species']
    weights = np.array(params.get('weights',[1.]*len(species)))
    edges = np.cumsum(weights / weights.sum())
    vertical = params.get('vertical',True)
    coords = np.arange(h*w)
    axis = (coords%w)/w if vertical else (coords//w)/h
    owner = np.searchsorted(edges,axis,side='right')
    ground = (sim.terrain==0) & (sim.soil<2)
    queues = []
    pools = []
    for i,name in enumerate(species):
        idx = BY_NAME[name]['index']
        cells = coords[ground & (owner==i)]
        stride = params.get('strides',{}).get(name,7)
        if name in ('Crimson Vine','Skyvine'):
            lattice = (cells//w)%stride == stride//2
        elif name in ('Rose Bush','Silver Fern'):
            lattice = (cells%w)%stride == stride//2
        else:
            lattice = ((cells//w)%stride==stride//2) & ((cells%w)%stride==stride//2)
        seeds = cells[lattice]
        # Prioritize trees first, then slow directional spreaders.
        if params.get('reverse',False):
            seeds = seeds[::-1]
        queues.append(list(map(int,seeds)))
        pools.append(cells)
    cursors = [0]*len(species)
    started = end-params.get('window',99)
    actions = {}
    # Cheap helper plants unlock Crimson and the common animal effects.
    starter_coords = coords[ground]
    anchor = int(starter_coords[len(starter_coords)//2])
    starter = [(12,int(p//w),int(p%w)) for p in starter_coords[::max(1,len(starter_coords)//12)][:10]]
    starter += [(2,anchor//w,anchor%w),(6,(anchor+1)//w,(anchor+1)%w)]
    rng = random.Random(params.get('seed',1))
    # Optional early Rose patch for Orange Blossom / Ironthorn unlocks.
    nursery = params.get('nursery',0)
    early = {}
    if nursery:
        rose_cells = coords[ground & ((coords%w)<max(2,int(w*nursery)))]
        rose_cells = rose_cells[(rose_cells%w)%12==3]
        early_start = end-params.get('nursery_window',190)
        for i,p in enumerate(rose_cells):
            early.setdefault(early_start+i//20,[]).append((2,int(p//w),int(p%w)))
    for t in range(end):
        acts = list(early.get(t,()))
        if t==started:
            acts += starter[:20-len(acts)]
        if t>=started:
            # Round-robin distributes available capacity to every unlocked territory.
            while len(acts)<20:
                before=len(acts)
                for i,name in enumerate(species):
                    if (name not in sim.unlocked or len(acts)>=20 or
                        t < started + params.get('delays',{}).get(name,0)):
                        continue
                    idx=BY_NAME[name]['index']
                    q=queues[i]
                    while cursors[i]<len(q):
                        p=q[cursors[i]];cursors[i]+=1
                        if sim.sp[p]!=idx and sim.can_occupy(name,p//w,p%w):
                            acts.append((idx,p//w,p%w))
                            break
                if len(acts)==before:
                    break
            # Use the remaining budget for gaps or undersupplied species.
            if t>=end-params.get('topup',45) and len(acts)<20:
                counts=sim.counts()
                order=sorted(range(len(species)),key=lambda i:counts.get(species[i],0)/max(1,len(pools[i])))
                taken={r*w+c for _,r,c in acts}
                for empty_only in (True,False):
                    for i in order:
                        name=species[i]
                        if (name not in sim.unlocked or len(acts)>=20 or
                            t < started + params.get('delays',{}).get(name,0)):
                            continue
                        idx=BY_NAME[name]['index']
                        possible=pools[i][sim.sp[pools[i]]==0] if empty_only else pools[i][sim.sp[pools[i]]!=idx]
                        # Seed gaps across the area, not all at the top edge.
                        if len(possible):
                            sample=possible[::max(1,len(possible)//100)]
                            offset=rng.randrange(len(sample))
                            sample=np.roll(sample,offset)
                            for p in sample:
                                p=int(p)
                                if p not in taken and sim.can_occupy(name,p//w,p%w):
                                    acts.append((idx,p//w,p%w));taken.add(p)
                                    if len(acts)>=20:break
                        if len(acts)>=20:break
                    if len(acts)>=20:break
        # Preserve the final write to each coordinate, with one placement per cell.
        last_write={(r,c):i for i,(_,r,c) in enumerate(acts)}
        acts=[a for i,a in enumerate(acts) if last_write[(a[1],a[2])]==i]
        if acts:
            actions[t]=acts
        sim.step(acts)
    return actions,sim


def robust_metrics(sim):
    return {f'a{a}_k{k}':sim.score(a,k)['final'] for a in (.5,1.,2.,3.) for k in (.5,1.,2.)}


def save_candidate(n,tag,actions,sim,params=None):
    assert not validate(actions,sim.L)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/f'LEVEL{n}_{tag}.json').write_text(json.dumps(to_submission(actions),separators=(',',':')),encoding='utf-8')
    summary={**sim.score(),'params':params,'sensitivity':robust_metrics(sim),'unlock_log':sim.log}
    (OUT/f'LEVEL{n}_{tag}_metrics.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    np.savez_compressed(OUT/f'LEVEL{n}_{tag}_state.npz',sp=sim.sp,age=sim.age,nut=sim.nut)
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--levels',nargs='+',type=int,default=[2,3,4])
    parser.add_argument('--rounds',type=int,default=12)
    args=parser.parse_args()
    rng=random.Random(731)
    for n in args.levels:
        level=load_level(f'data/level{n}.json')
        base_actions=read_actions(n)
        base=FastSimulator(level).run(base_actions)
        best=base.score()['final']
        save_candidate(n,'original',base_actions,base)
        print('BASELINE',n,json.dumps(base.score()),flush=True)
        winter=level.ticks==800
        choices = [
            ['Grass','Razorgrass','Crimson Vine','Crystal Cactus','Dwarf Sunflower','Oak Tree'],
            ['Grass','Crimson Vine','Dwarf Sunflower','Oak Tree','Crystal Cactus'],
            ['Grass','Razorgrass','Crimson Vine','Dwarf Sunflower','Oak Tree'],
        ] if winter else [
            ['Grass','Rose Bush','Lavender','Crimson Vine','Dwarf Sunflower','Oak Tree','Razorgrass'],
            ['Grass','Rose Bush','Lavender','Dwarf Sunflower','Oak Tree'],
            ['Grass','Rose Bush','Orange Blossom','Lavender','Crimson Vine','Dwarf Sunflower','Oak Tree'],
        ]
        for trial in range(args.rounds):
            species=list(choices[trial%len(choices)])
            if trial>=3:rng.shuffle(species)
            params={'species':species,'weights':[rng.uniform(.7,1.4) for _ in species],
                    'vertical':trial%4!=3,'window':rng.choice([99,99,95,110]),
                    'strides':{s:rng.choice([5,7,9,11]) for s in species},
                    'topup':rng.choice([35,50,65]),'seed':trial}
            params['strides']['Crimson Vine']=rng.choice([25,35,45])
            params['strides']['Rose Bush']=rng.choice([12,18,24])
            params['strides']['Oak Tree']=rng.choice([5,7,9])
            start=time.perf_counter()
            acts,sim=balanced_plan(level,params)
            score=sim.score()
            print('TRIAL',n,trial,round(score['final'],5),score['C'],score['counts'],
                  'sec',round(time.perf_counter()-start,2),flush=True)
            if score['final']>best:
                best=score['final']
                save_candidate(n,'candidate',acts,sim,params)
                print('NEW BEST',n,best,flush=True)


if __name__=='__main__':main()
