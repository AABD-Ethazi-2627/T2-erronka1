"""Reproduce the fixed-pair selection from historical screening OOF, not outer."""
from pathlib import Path
import hashlib
import io
import itertools
import json
import zipfile

import numpy as np
import pandas as pd

P=Path(__file__).resolve().parent
ROOT=P.parents[1]
SOURCE=ROOT/'docs/evidence/CG34_20261023'
m=json.loads((SOURCE/'manifest.json').read_text())
archive=SOURCE/'raw-evidence.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='640d75114324df4d8bafa20461cccf20da3850552c3bd6fa48080b9584e97896'
train=pd.read_csv(ROOT/'data/ai4i2020_train.csv',float_precision='round_trip').loc[m['membership']['train']]
by={};units=[]
with zipfile.ZipFile(archive) as z:
    for n in z.namelist():
        if not n.startswith('units/') or not n.endswith('/task.json'):continue
        raw=z.read(n);t=json.loads(raw)
        if t['phase']!='screening' or next(s for s in m['catalog'] if s['name']==t['model'])['anomaly']:continue
        pref=n[:-9];r=json.loads(z.read(pref+'result.json'));raw_score=z.read(pref+'scores.csv')
        assert hashlib.sha256(raw).hexdigest()==r['task_sha256']
        assert hashlib.sha256(raw_score).hexdigest()==r['scores_sha256']
        assert t['fit']==m['screening'][t['fold']]['fit'] and t['held']==m['screening'][t['fold']]['held']
        assert not set(t['fit'])&set(t['held']) and set(t['fit']+t['held'])==set(train.index)
        d=pd.read_csv(io.BytesIO(raw_score),float_precision='round_trip').set_index('source_row_index')
        assert d.index.tolist()==t['held'] and np.array_equal(d.label.to_numpy(),train.loc[d.index,'machine_failure'])
        if t['model'].startswith('xgb_'):d['score']=d.score.to_numpy().astype(np.float32).astype(float)
        by.setdefault(t['model'],[]).append(d)
        units.append({'path':pref,'task_sha256':r['task_sha256'],'scores_sha256':r['scores_sha256']})
frames={n:pd.concat(v).sort_index() for n,v in by.items()}
for n,f in frames.items(): assert len(f)==5600 and not f.index.duplicated().any() and set(f.index)==set(train.index)
y=frames['rf_reference'].label.to_numpy();rows=[]
for a,b in itertools.combinations(by,2):
    for w in [.25,.5,.75]:
        pred=w*frames[a].score.to_numpy()+(1-w)*frames[b].score.to_numpy()>=.15
        tp=int(np.sum(pred&(y==1)));fn=190-tp;fp=int(np.sum(pred&(y==0)))
        rows.append(dict(a=a,b=b,weight_a=w,tp=tp,fn=fn,fp=fp,cost=5000*fn+200*fp+300*tp))
rows.sort(key=lambda r:(r['cost'],r['fn'],r['a'],r['b'],r['weight_a']))
old=json.loads((P/'run-01/seleccion-fija-screening.json').read_text())
assert rows==old['ranking'] and rows[0]==old['winner']
(P/'run-01/VERIFICACION_SELECCION_FIJA.json').write_text(json.dumps({'status':'passed','source_screening_units':len(units),'pairs_checked':len(rows),'winner':rows[0],'ranking_reproduced_exactly':True,'units':units},indent=2))
print('Fixed selection reproduced exactly:',rows[0])
