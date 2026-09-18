"""Re-score candidates through the original engine without changing its rules."""
import argparse
import json
import time
from functools import lru_cache
from pathlib import Path
from photospheria import load_level
from photospheria.engine import Simulator
from photospheria.catalogue import BY_NAME
from photospheria.submission import from_submission, validate


class CachedReference(Simulator):
    """Caches immutable lookups only; Simulator.step/place/score are unchanged."""
    def rules_of(self, species):
        if not hasattr(self,'_rules'):self._rules={}
        if species not in self._rules:self._rules[species]=super().rules_of(species)
        return self._rules[species]

    def growth_of(self, species):
        if not hasattr(self,'_growth_cache'):self._growth_cache={}
        key=(species,self.season)
        if key not in self._growth_cache:self._growth_cache[key]=super().growth_of(species)
        return self._growth_cache[key]

    def animal_mods(self, species):
        if not hasattr(self,'_animal_cache'):self._animal_cache={}
        key=(species,frozenset(self.animals))
        if key not in self._animal_cache:self._animal_cache[key]=super().animal_mods(species)
        return self._animal_cache[key]


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--levels',nargs='+',type=int,default=[1,2,3,4]);args=ap.parse_args()
    out=Path('out/optimization')
    for n in args.levels:
        actions=from_submission(json.loads((out/f'LEVEL{n}_candidate.json').read_text()))
        level=load_level(f'data/level{n}.json')
        assert not validate(actions,level)
        for t,plants in actions.items():
            assert len({(r,c) for _,r,c in plants})==len(plants), ('duplicate cell',n,t)
        expected=json.loads((out/f'LEVEL{n}_candidate_metrics.json').read_text())
        sim=CachedReference(level)
        start=time.perf_counter()
        print('VERIFY',n,flush=True)
        for t in range(level.ticks):
            sim.step(actions.get(t,()))
            if t%100==99:print('Level',n,'tick',t+1,flush=True)
        actual=sim.score()
        assert abs(actual['final']-expected['final'])<1e-12,(actual,expected)
        assert sim.rejected==0,(n,sim.rejected)
        result={'score':actual,'rejected':sim.rejected,'seconds':time.perf_counter()-start,
                'matches_fast_evaluator_score':True}
        (out/f'LEVEL{n}_verified.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print('VERIFIED',n,actual['final'],actual['counts'],round(result['seconds'],2),'seconds',flush=True)
