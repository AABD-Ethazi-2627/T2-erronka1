"""Sensitivity to costs/recall; all cutoffs and model choices use inner only."""
from pathlib import Path
import hashlib
import itertools
import json
import time
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import estudio

P=Path(__file__).resolve().parent
OUT=P/'sensibilidad'
ROOT=P.parents[1]

def outcome(y,s,t,c):
    pr=s>=t
    tp=int(np.sum(pr&(y==1)));fp=int(np.sum(pr&(y==0)))
    fn=int(np.sum(~pr&(y==1)));tn=int(np.sum(~pr&(y==0)))
    return dict(tp=tp,fp=fp,fn=fn,tn=tn,n=len(y),recall=tp/max(tp+fn,1),precision=tp/max(tp+fp,1),cost=c['tp']*tp+c['fp']*fp+c['fn']*fn+c['tn']*tn)

def cuts(y,s):
    order=np.argsort(-s,kind='stable')
    ends=np.r_[np.flatnonzero(np.diff(s[order])),len(s)-1]
    tp=np.r_[0,np.cumsum(y[order])[ends]]
    fp=np.r_[0,np.cumsum(1-y[order])[ends]]
    thresholds=np.r_[np.nextafter(s.max(),np.inf),s[order[ends]]]
    return thresholds,tp,fp,int(y.sum())-tp,int((y==0).sum())-fp

def best_threshold(y,s,c):
    ts,tp,fp,fn,tn=cuts(y,s)
    costs=c['tp']*tp+c['fp']*fp+c['fn']*fn+c['tn']*tn
    eligible=np.flatnonzero(tp/max(y.sum(),1)>=c['min_recall'])
    k=min(eligible,key=lambda k:(costs[k],fn[k],-ts[k]))
    return float(ts[k]),int(costs[k]),int(fn[k])

def run():
    start=time.perf_counter()
    destination=OUT/'resultados.csv'
    if destination.exists():raise FileExistsError('Preserve prior sensitivity output')
    config=json.loads((OUT/'protocolo.json').read_text())
    m=json.loads((ROOT/'docs/evidence/CG34_20261023/manifest.json').read_text())
    source=ROOT/'data/ai4i2020_train.csv'
    assert estudio.sha(source.read_bytes())==m['source_sha256']
    train=pd.read_csv(source,float_precision='round_trip').loc[m['membership']['train']]
    archive=ROOT/'docs/evidence/CG34_20261023/raw-evidence.zip'
    assert estudio.sha(archive.read_bytes())=='640d75114324df4d8bafa20461cccf20da3850552c3bd6fa48080b9584e97896'
    matrices,verified=estudio.load_archive(archive,m,train)
    indices=[i for i,s in enumerate(m['catalog']) if not s['anomaly']]
    pairs=[(a,b,w) for a,b in itertools.combinations(indices,2) for w in (.25,.5,.75)]
    selections=[];aggregate=[]
    for fold in range(3):
        ids_i=m['outer'][fold]['fit'];ids_o=m['outer'][fold]['held']
        yi=train.loc[ids_i,'machine_failure'].to_numpy();yo=train.loc[ids_o,'machine_failure'].to_numpy()
        mi=matrices[(fold,'inner')];mo=matrices[(fold,'outer')]
        best={}
        def evaluate(name,category,si,so,members,constant=False):
            ts,tp,fp,fn,tn=cuts(yi,si)
            for scenario in config['scenarios']:
                costs=scenario['tp']*tp+scenario['fp']*fp+scenario['fn']*fn+scenario['tn']*tn
                eligible=np.flatnonzero(tp/max(yi.sum(),1)>=scenario['min_recall'])
                if constant:
                    threshold=.5
                    inside=outcome(yi,si,threshold,scenario)
                    key=(int(inside['recall']<scenario['min_recall']),inside['cost'],inside['fn'],name)
                else:
                    k=min(eligible,key=lambda k:(costs[k],fn[k],-ts[k]));threshold=float(ts[k])
                    inside=outcome(yi,si,threshold,scenario)
                    key=(0,int(costs[k]),int(fn[k]),name)
                pools=[category]+(['RF'] if name=='single:rf_reference' else [])
                for pool in pools:
                    lookup=(scenario['id'],pool)
                    if lookup not in best or key<best[lookup]['key']:
                        best[lookup]=dict(key=key,fold=fold,scenario=scenario['id'],procedure=pool,name=name,members=members,threshold=threshold,inner=inside,outer=outcome(yo,so,threshold,scenario))
        for i in indices:
            sp=m['catalog'][i]
            evaluate('single:'+sp['name'],'single',mi[:,i],mo[:,i],[sp['name']],sp['family']=='dummy')
        for a,b,w in pairs:
            aa=m['catalog'][a]['name'];bb=m['catalog'][b]['name']
            evaluate(f'pair:{aa}+{bb}@{w}','pair',w*mi[:,a]+(1-w)*mi[:,b],w*mo[:,a]+(1-w)*mo[:,b],[aa,bb])
        selections.extend({k:v for k,v in x.items() if k!='key'} for x in best.values())
        print('Sensitivity outer',fold,'complete',flush=True)
    for s in config['scenarios']:
        for pool in ('RF','single','pair'):
            part=[x for x in selections if x['scenario']==s['id'] and x['procedure']==pool]
            assert len(part)==3
            total={k:sum(x['outer'][k] for x in part) for k in ('n','tp','fn','fp','tn','cost')}
            aggregate.append(dict(scenario=s['id'],procedure=pool,**total,recall=total['tp']/190,precision=total['tp']/max(total['tp']+total['fp'],1),cost_per_1000=total['cost']*1000/5600,thresholds=' / '.join(f"{x['threshold']:.9g}" for x in part)))
    pd.DataFrame(aggregate).to_csv(destination,index=False)
    (OUT/'selecciones.json').write_text(json.dumps(selections,indent=2,allow_nan=False))
    (OUT/'ejecucion.json').write_text(json.dumps({'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'protocol_sha256':hashlib.sha256((OUT/'protocolo.json').read_bytes()).hexdigest(),'source_units_verified':len(verified),'scenarios':9,'configurations_per_scenario':2380,'folds':3,'selections':len(selections),'no_new_fits':True,'no_validation_or_test_scoring':True,'wall_seconds':time.perf_counter()-start},indent=2))
    print(pd.DataFrame(aggregate).to_string(index=False))

if __name__=='__main__':
    with threadpool_limits(limits=1):run()
