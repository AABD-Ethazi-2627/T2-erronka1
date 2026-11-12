"""Inner-constrained marked-observation budgets plus uncertainty of policy A."""
import json,time,itertools,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from threadpoolctl import threadpool_limits
import estudio,politicas
P=Path(__file__).resolve().parent;ROOT=P.parents[1];OUT=P/'capacidad'

def run():
 begin=time.perf_counter();cfg=json.load(open(OUT/'protocolo.json'))
 if (OUT/'resultados.json').exists():raise FileExistsError('preserve existing result')
 m=json.load(open(ROOT/'docs/evidence/CG34_20261023/manifest.json'))
 source=ROOT/'data/ai4i2020_train.csv';assert estudio.sha(source.read_bytes())==m['source_sha256']
 train=pd.read_csv(source,float_precision='round_trip').loc[m['membership']['train']]
 arc=ROOT/'docs/evidence/CG34_20261023/raw-evidence.zip';assert estudio.sha(arc.read_bytes())=='640d75114324df4d8bafa20461cccf20da3850552c3bd6fa48080b9584e97896'
 matrix,verified=estudio.load_archive(arc,m,train);indices=[i for i,s in enumerate(m['catalog']) if not s['anomaly']]
 selections=[]
 for fold in range(3):
  ids_i=m['outer'][fold]['fit'];ids_o=m['outer'][fold]['held'];yi=train.loc[ids_i,'machine_failure'].to_numpy();yo=train.loc[ids_o,'machine_failure'].to_numpy();mi=matrix[(fold,'inner')];mo=matrix[(fold,'outer')]
  best={}
  def evaluate(name,group,si,so):
   ts,tp,fp,fn,tn=politicas.cuts(yi,si);cost=cfg['cost']['tp']*tp+cfg['cost']['fp']*fp+cfg['cost']['fn']*fn+cfg['cost']['tn']*tn
   for budget in cfg['budgets_per_1000']:
    eligible=np.flatnonzero((tp/yi.sum()>=cfg['min_inner_recall'])&((tp+fp)*1000/len(yi)<=budget))
    if not len(eligible):continue
    k=min(eligible,key=lambda k:(cost[k],fn[k],-ts[k]));cut=float(ts[k]);key=(int(cost[k]),int(fn[k]),name)
    for pool in [group]+(['RF'] if name=='single:rf_reference' else []):
     lookup=(budget,pool)
     if lookup not in best or key<best[lookup]['key']:
      inside=politicas.outcome(yi,si,cut,cfg['cost']);outside=politicas.outcome(yo,so,cut,cfg['cost'])
      best[lookup]=dict(key=key,fold=fold,budget=budget,procedure=pool,name=name,threshold=cut,inner=inside,outer=outside,inner_marked_per_1000=1000*(inside['tp']+inside['fp'])/inside['n'],outer_marked_per_1000=1000*(outside['tp']+outside['fp'])/outside['n'])
  for i in indices:evaluate('single:'+m['catalog'][i]['name'],'single',mi[:,i],mo[:,i])
  for a,b in itertools.combinations(indices,2):
   for w in (.25,.5,.75):evaluate(f'pair:{m["catalog"][a]["name"]}+{m["catalog"][b]["name"]}@{w}','pair',w*mi[:,a]+(1-w)*mi[:,b],w*mo[:,a]+(1-w)*mo[:,b])
  for budget in cfg['budgets_per_1000']:
   for pool in ('RF','single','pair'):
    v=best.get((budget,pool));selections.append({k:x for k,x in v.items() if k!='key'} if v else dict(fold=fold,budget=budget,procedure=pool,unavailable=True,reason='no inner cutoff satisfies recall and marked-observation budget'))
  print('budget outer',fold,'complete',flush=True)
 rows=[]
 for budget in cfg['budgets_per_1000']:
  for pool in ('RF','single','pair'):
   parts=[x for x in selections if x['budget']==budget and x['procedure']==pool];valid=[x for x in parts if not x.get('unavailable')]
   row=dict(budget=budget,procedure=pool,feasible_folds=len(valid),available=len(valid)==3)
   if len(valid)==3:
    counts={k:sum(x['outer'][k] for x in valid) for k in ('n','tp','fp','fn','tn','cost')};row.update(**counts,recall=counts['tp']/190,marked_per_1000=(counts['tp']+counts['fp'])*1000/5600,cost_per_1000=counts['cost']*1000/5600)
   rows.append(row)
 (OUT/'resultados.json').write_text(json.dumps(dict(rows=rows,selections=selections),indent=2))
 # Conditional uncertainty for A specifically, not the old interval for policy B.
 base=pd.read_csv(P/'run-01/single-rf_reference-A-oof.csv',float_precision='round_trip').set_index('source_row_index').sort_index();y=base.label.to_numpy();a=base.prediction.to_numpy().astype(bool);pos=np.flatnonzero(y);neg=np.flatnonzero(y==0)
 uncertainty=[]
 for name in ['all','single','pair','triple','committee','stack']:
  cand=pd.read_csv(P/f'run-01/selector-{name}-A-oof.csv',float_precision='round_trip').set_index('source_row_index').sort_index();assert cand.index.equals(base.index) and cand.label.equals(base.label)
  b=cand.prediction.to_numpy().astype(bool);rng=np.random.default_rng(42);delta=[]
  for _ in range(2000):
   ix=np.r_[rng.choice(pos,len(pos)),rng.choice(neg,len(neg))];yi=y[ix];aa=a[ix];bb=b[ix]
   ca=5000*np.sum((yi==1)&~aa)+200*np.sum((yi==0)&aa)+300*np.sum((yi==1)&aa);cb=5000*np.sum((yi==1)&~bb)+200*np.sum((yi==0)&bb)+300*np.sum((yi==1)&bb);delta.append((cb-ca)*1000/len(ix))
  folds=[]
  for fold,g in cand.groupby('fold'):
   ref=base.loc[g.index];cb=politicas.outcome(g.label.to_numpy(),g.score.to_numpy(),g.threshold.to_numpy(),cfg['cost']);ca=politicas.outcome(ref.label.to_numpy(),ref.score.to_numpy(),ref.threshold.to_numpy(),cfg['cost']);folds.append(dict(fold=int(fold),cost_delta_per_1000=(cb['cost']-ca['cost'])*1000/len(g),candidate_ap=float(average_precision_score(g.label,g.score)),reference_ap=float(average_precision_score(ref.label,ref.score)),**cb))
  uncertainty.append(dict(procedure=name,policy='A',delta_cost_ci95=np.quantile(delta,[.025,.975]).tolist(),folds=folds,mean_fold_ap=float(np.mean([f['candidate_ap'] for f in folds]))))
 (OUT/'incertidumbre-A.json').write_text(json.dumps(dict(method='paired stratified bootstrap, 2000 resamples seed42 of fixed OOF predictions; conditional descriptive, excludes training/search variability and fold dependence',comparisons=uncertainty),indent=2))
 (OUT/'ejecucion.json').write_text(json.dumps(dict(code_sha256=estudio.sha(Path(__file__).read_bytes()),protocol_sha256=estudio.sha((OUT/'protocolo.json').read_bytes()),source_units=len(verified),wall_seconds=time.perf_counter()-begin,no_new_fits=True,no_validation_or_test_scoring=True),indent=2))
 print(json.dumps(rows),flush=True)

if __name__=='__main__':
 with threadpool_limits(limits=1):run()
