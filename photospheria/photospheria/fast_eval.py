"""Compiled evaluator matching engine.py, for reproducible strategy experiments.

This accelerates the local replica; it does not claim to be the hidden judge.
Only the rules implemented by engine.py are modelled in legacy mode.
"""
import math
import numpy as np
from numba import njit
from .catalogue import (PLANTS, BY_INDEX, BY_NAME, N_SPECIES, STARTERS,
                        WorldView, present_animals, unlocked_plants, BURNT)
from .engine import Simulator, pattern_offsets


@njit(cache=True)
def neighbours(sp, r, c, h, w):
    n = 0
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            rr, cc = r + dr, c + dc
            if (dr or dc) and 0 <= rr < h and 0 <= cc < w and sp[rr*w+cc]:
                n += 1
    return n


@njit(cache=True)
def can(s, pos, sp, nut, soil, terrain, shade, rule, h, w):
    if terrain[pos] != 0 and not (terrain[pos] == 3 and rule[s, 6]):
        return False
    if not (int(rule[s, 18]) & (1 << soil[pos])) or nut[pos] <= 0:
        return False
    if rule[s, 0] and shade[pos] and not rule[s, 7]:
        return False
    if rule[s, 1] and not shade[pos]:
        return False
    if rule[s, 2] and soil[pos] != 3:
        return False
    r, c = pos // w, pos % w
    feat = rule[s, 3]
    if feat:
        found = False
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            rr, cc = r+dr, c+dc
            if 0 <= rr < h and 0 <= cc < w:
                terr = terrain[rr*w+cc]
                if (feat == 1 and terr == 2) or (feat == 2 and (terr == 1 or terr == 4)):
                    found = True
        if not found:
            return False
    if rule[s, 4] and neighbours(sp, r, c, h, w):
        return False
    return True


@njit(cache=True)
def place(s, pos, sp, age, mat, nut, dead, sub, soil, terrain, shade, rule, h, w, retain_dead):
    if not can(s, pos, sp, nut, soil, terrain, shade, rule, h, w):
        return False
    if sp[pos] and sp[pos] != s and rule[s, 5]:
        sub[pos] = s
        return True
    sp[pos], age[pos], mat[pos] = s, 0, False
    if not retain_dead:
        dead[pos] = False
    return True


@njit(cache=True)
def kill(pos, sp, age, mat, dead, sub):
    if sub[pos]:
        sp[pos], sub[pos] = sub[pos], 0
        age[pos], mat[pos] = 0, False
    else:
        sp[pos], age[pos], mat[pos], dead[pos] = 0, 0, False, True


@njit(cache=True)
def tick_kernel(sp, age, mat, nut, dead, sub, soil, terrain, shade, rule,
                growth, offsets, offcount, actions, unlocked, winter, h, w, retain_dead,
                mature_competition=False):
    rejected = 0
    for j in range(min(20, len(actions))):
        s, r, c = actions[j]
        if (s < 1 or s >= len(unlocked) or not unlocked[s] or
            not (0 <= r < h and 0 <= c < w)):
            rejected += 1
        elif not place(s, r*w+c, sp, age, mat, nut, dead, sub, soil, terrain,
                       shade, rule, h, w, retain_dead):
            rejected += 1
    for pos in range(len(sp)):
        s = sp[pos]
        if not s:
            continue
        age[pos] += 1
        ttm = growth[s, 0]
        if rule[s, 8] or rule[s, 9]:
            n = neighbours(sp, pos//w, pos%w, h, w)
            ttm += (rule[s, 9] - rule[s, 8]) * n
        if rule[s, 10] and soil[pos] == 3:
            ttm -= rule[s, 10]
        mat[pos] = age[pos] >= max(1, ttm)
    shade[:] = False
    for pos in range(len(sp)):
        s = sp[pos]
        if not s or not mat[pos]:
            continue
        rad = rule[s, 11]
        if rad:
            r, c = pos//w, pos%w
            for rr in range(max(0, r-rad), min(h, r+rad+1)):
                for cc in range(max(0, c-rad), min(w, c+rad+1)):
                    shade[rr*w+cc] = True
    for pos in range(len(sp)):
        s = sp[pos]
        if not s or not mat[pos]:
            continue
        rad = rule[s, 12]
        if rad:
            r, c = pos//w, pos%w
            for rr in range(max(0, r-rad), min(h, r+rad+1)):
                for cc in range(max(0, c-rad), min(w, c+rad+1)):
                    if rr*w+cc != pos:
                        soil[rr*w+cc] = 3
    births = [(0, 0)]
    births.pop()
    for pos in range(len(sp)):
        s = sp[pos]
        if not s or not mat[pos] or (winter and rule[s, 13]) or (shade[pos] and rule[s, 14]):
            continue
        if age[pos] % int(growth[s, 1]):
            continue
        r, c = pos//w, pos%w
        for k in range(offcount[s]):
            rr, cc = r+offsets[s,k,0], c+offsets[s,k,1]
            if 0 <= rr < h and 0 <= cc < w:
                dest = rr*w+cc
                if sp[dest] == s or (rule[s, 15] and not dead[dest]):
                    continue
                births.append((s, dest))
    for s, dest in births:
        if (mature_competition and sp[dest] and mat[dest]
                and rule[s,19] < rule[sp[dest],19]):
            continue
        place(s, dest, sp, age, mat, nut, dead, sub, soil, terrain,
              shade, rule, h, w, retain_dead)
    for pos in range(len(sp)):
        if sp[pos]:
            nut[pos] -= 0.5 if dead[pos] else 1.0
            if nut[pos] <= 0:
                nut[pos] = 0
                kill(pos, sp, age, mat, dead, sub)
        elif dead[pos]:
            nut[pos] = min(100., nut[pos] + 1.)
    doomed = np.zeros(len(sp), np.bool_)
    for pos in range(len(sp)):
        s = sp[pos]
        if not s:
            continue
        if rule[s, 16] or rule[s, 17] < 9:
            nb = neighbours(sp, pos//w, pos%w, h, w)
            if (rule[s, 16] and nb == 0) or nb > rule[s, 17]:
                doomed[pos] = True
        if rule[s, 0] and shade[pos] and not rule[s, 7]:
            doomed[pos] = True
        if rule[s, 1] and not shade[pos]:
            doomed[pos] = True
    counts = np.zeros(rule.shape[0], np.int64)
    features = np.zeros(2, np.int64)
    for pos in range(len(sp)):
        if doomed[pos]:
            kill(pos, sp, age, mat, dead, sub)
        counts[sp[pos]] += 1
        features[0] += dead[pos]
        features[1] += soil[pos] == 3
    return counts, features, rejected


def rules_array():
    rules = np.zeros((max(BY_INDEX)+1, 20), dtype=np.int64)
    rules[:,17] = 9
    names = {"no_shade_survival":0,"shade_required":1,"must_be_burnt_soil":2,
             "no_adjacent_plants":4,"subsurface_growth":5,"crack_spread":6,
             "can_grow_in_shade":7,"adjacent_maturity_boost":8,
             "adjacent_maturity_penalty":9,"burnt_soil_maturity_boost":10,
             "shade_radius":11,"burnt_soil_radius":12,"no_winter_spread":13,
             "no_shade_spread":14,"dead_matter_only_spread":15,"die_if_isolated":16,
             "die_if_neighbors_greater_than":17}
    for plant in PLANTS:
        idx = plant["index"]
        for rule in plant["rules"]["weaknesses"] + plant["rules"]["special"]:
            key = rule["type"]
            if key in names:
                rules[idx,names[key]] = rule.get("value", 1)
            elif key == "must_be_adjacent_to":
                rules[idx,3] = {"water":1,"rock_or_path":2}[rule["feature"]]
        rules[idx,18] = sum(1 << soil for soil in plant["preferred_soil"])
        rules[idx,19] = plant['growth']['invasiveness_rank']
    return rules


class FastSimulator:
    def __init__(self, level, retain_dead=False, mature_competition=False):
        self.L = level
        n = level.cells_total
        self.sp = np.zeros(n, np.int64)
        self.age = np.zeros(n, np.int64)
        self.mat = np.zeros(n, np.bool_)
        self.nut = np.full(n, 100., np.float64)
        self.dead = np.zeros(n, np.bool_)
        self.sub = np.zeros(n, np.int64)
        self.soil = np.array(level.soil, np.int64).ravel()
        tm = {"soil":0,"path":1,"water":2,"crack":3,"stone":4,"void":5}
        self.terrain = np.array([[tm[x] for x in r] for r in level.terrain], np.int64).ravel()
        self.shade = np.zeros(n, np.bool_)
        self.rule = rules_array()
        self.tick = 0
        self.season = level.seasons.get(0,"Spring")
        self.animals = set()
        self.unlocked = set(STARTERS)
        self.events_fired = set()
        self.rejected = 0
        self.log = []
        self._counts = np.zeros(len(self.rule), np.int64)
        self._features = np.zeros(2, np.int64)
        self._cache = {}
        self._helper = Simulator(level)
        self.retain_dead = retain_dead
        self.mature_competition = mature_competition

    def counts(self):
        return {BY_INDEX[i]["plant"]:int(v) for i,v in enumerate(self._counts) if i and v}

    def _growth(self):
        key = (self.season, frozenset(self.animals))
        if key not in self._cache:
            self._helper.season = self.season
            self._helper.animals = self.animals
            growth = np.zeros((len(self.rule),2), np.float64)
            all_offsets = {}
            for idx, plant in BY_INDEX.items():
                name = plant["plant"]
                g = self._helper.growth_of(name)
                sr, mat, rng = self._helper.animal_mods(name)
                growth[idx] = [g["time_to_maturity"]/max(mat,1e-6), max(1,round(g["spread_rate"]/sr))]
                all_offsets[idx] = pattern_offsets(g["spread_type"],max(1,int(g["spread_range"]*rng)))
            offcount = np.zeros(len(self.rule), np.int64)
            offsets = np.zeros((len(self.rule),max(map(len,all_offsets.values())),2), np.int64)
            for idx, values in all_offsets.items():
                offcount[idx] = len(values)
                offsets[idx,:len(values)] = values
            self._cache[key] = growth, offsets, offcount
        return self._cache[key]

    def step(self, actions=()):
        if self.tick in self.L.seasons:
            self.season = self.L.seasons[self.tick]
        if self.tick in self.L.events:
            self.events_fired.add(self.L.events[self.tick])
        growth, offsets, offcount = self._growth()
        unlocked = np.zeros(len(self.rule),np.bool_)
        for name in self.unlocked:
            unlocked[BY_NAME[name]["index"]] = True
        actions = np.asarray(actions,dtype=np.int64).reshape((-1,3))
        self._counts, self._features, rejected = tick_kernel(
            self.sp,self.age,self.mat,self.nut,self.dead,self.sub,self.soil,self.terrain,
            self.shade,self.rule,growth,offsets,offcount,actions,unlocked,
            self.season=="Winter",self.L.height,self.L.width,self.retain_dead,
            self.mature_competition)
        self.rejected += rejected
        counts = self.counts()
        pop = sum(counts.values())
        world = WorldView(counts,self.L.cells_total,set(self.animals),self.events_fired,
                          {"dead_matter":int(self._features[0]),"burnt_soil":int(self._features[1])},
                          max(counts.values())/pop if pop else 0.)
        self.animals = present_animals(world) if self.L.animals_enabled else set()
        world.animals = self.animals
        newly = unlocked_plants(world) - self.unlocked
        if newly:
            self.log.append((self.tick,"UNLOCK",sorted(newly)))
        self.unlocked |= newly
        self.tick += 1

    def run(self, actions):
        for t in range(self.L.ticks):
            self.step(actions.get(t,()))
        return self

    def can_occupy(self, name, r, c):
        if not (0 <= r < self.L.height and 0 <= c < self.L.width):
            return False
        return can(BY_NAME[name]["index"],r*self.L.width+c,self.sp,self.nut,self.soil,
                   self.terrain,self.shade,self.rule,self.L.height,self.L.width)

    def score(self, alpha=1., k=1.):
        counts = self.counts()
        total = sum(counts.values())
        entropy = -sum((v/total)*math.log(v/total,N_SPECIES) for v in counts.values()) if total else 0.
        fill = total/self.L.cells_total
        longevity = float(np.sum((self.age[self.sp>0]/self.L.ticks)**k)/self.L.cells_total)
        return {"final":0.8*entropy*fill**alpha+0.2*longevity,"H":entropy,
                "C":total,"Cmax":self.L.cells_total,"size":fill,"longevity":longevity,
                "counts":counts,"species":len(counts),"unlocked":len(self.unlocked),
                "animals":sorted(self.animals),"rejected":self.rejected}
