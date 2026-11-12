"""Historical fixed configuration: explicitly post-selection, not refit evaluation."""
from pathlib import Path
import json,io,hashlib,zipfile
import pandas as pd
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
ST=ROOT/'exports/estudio-multimodelo-2026-11-04'
archive=ROOT/'docs/evidence/CG34_20261023/raw-evidence.zip'
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
assert digest=='640d75114324df4d8bafa20461cccf20da3850552c3bd6fa48080b9584e97896'
frames=[];provenance=[]
with zipfile.ZipFile(archive) as z:
 for name in ['cart_depth3','lgb_7_True']:
  path='analysis-v1/'+name+'-outer.csv';raw=z.read(path)
  f=pd.read_csv(io.BytesIO(raw),float_precision='round_trip').set_index('source_row_index').sort_index()
  frames.append(f);provenance.append({'path':path,'sha256':hashlib.sha256(raw).hexdigest()})
a,b=frames
assert len(a)==5600 and a.index.equals(b.index) and a.label.equals(b.label)
ref=pd.read_csv(ST/'run-01/single-rf_reference-B-oof.csv',float_precision='round_trip').set_index('source_row_index').sort_index()
assert ref.index.equals(a.index) and ref.label.equals(a.label)
y=a.label.to_numpy();score=.75*a.score.to_numpy()+.25*b.score.to_numpy();pred=score>=.15;rp=ref.prediction.to_numpy().astype(bool)
def counts(p):
 tp=int(np.sum(p&(y==1)));fn=int(np.sum(~p&(y==1)));fp=int(np.sum(p&(y==0)));tn=int(np.sum(~p&(y==0)))
 return dict(tp=tp,fn=fn,fp=fp,tn=tn,cost=300*tp+5000*fn+200*fp,n=len(y))
c=counts(pred);r=counts(rp);assert (c['tp'],c['fn'],c['fp'],c['tn'],c['cost'])==(168,22,40,5370,168400)
pos=np.flatnonzero(y);neg=np.flatnonzero(y==0);rng=np.random.default_rng(42);delta=[]
for _ in range(2000):
 ix=np.r_[rng.choice(pos,len(pos)),rng.choice(neg,len(neg))];yy=y[ix];pp=pred[ix];rr=rp[ix]
 costs=lambda p:5000*np.sum((yy==1)&~p)+200*np.sum((yy==0)&p)+300*np.sum((yy==1)&p)
 delta.append((costs(pp)-costs(rr))*1000/len(ix))
result={'identity':'Historical CART depth3 + LightGBM7 balanced, weights 75/25, cutoff 0.15; post-selection configuration',
 'status':'post-selection development diagnostic, not independent; NOT evaluation of the newly refitted ensemble.joblib',
 'selection':'chosen from 2340 pairs on historical screening of the same original train rows',
 'counts':c,'reference':r,'cutoff':.15,'weights':[.75,.25],
 'cost_per_1000':c['cost']*1000/5600,'delta_vs_rf015_per_1000':(c['cost']-r['cost'])*1000/5600,
 'delta_ci95_conditional':np.quantile(delta,[.025,.975]).tolist(),
 'interval_method':'2000 paired stratified bootstrap samples seed42, fixed historical OOF scores; does not correct for selection among 2340 pairs, dependence or refit',
 'archive_sha256':digest,'sources':provenance,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'limits':['Not a blind test, new machine or future failure prediction.','No validation/excluded test used.','The refitted candidate remains tested for reload/inference only.']}
(OUT/'fuentes/fijo-postseleccion.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:result[k] for k in ['counts','delta_vs_rf015_per_1000','delta_ci95_conditional']}))
