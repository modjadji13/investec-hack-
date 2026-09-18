import json
from pathlib import Path
from photospheria import load_level
from photospheria.submission import from_submission,to_submission,validate

out=Path('out/optimization')
for n in range(1,5):
    path=out/f'LEVEL{n}_candidate.json'
    actions=from_submission(json.loads(path.read_text()))
    cleaned={}
    removed=0
    for t,plants in actions.items():
        last={(r,c):i for i,(_,r,c) in enumerate(plants)}
        cleaned[t]=[p for i,p in enumerate(plants) if last[(p[1],p[2])]==i]
        removed+=len(plants)-len(cleaned[t])
    if removed:
        level=load_level(f'data/level{n}.json')
        assert not validate(cleaned,level)
        temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(to_submission(cleaned),separators=(',',':')),encoding='utf-8')
        temporary.replace(path)
    print('Level',n,'redundant actions removed:',removed,flush=True)
