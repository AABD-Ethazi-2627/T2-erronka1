"""Independent arithmetic and selection audit; no use of estudio.counts."""
import csv
import importlib.util
import json
import math
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / 'run-01'


def read(p):
    with p.open() as f:
        return list(csv.DictReader(f))


def tally(rows):
    r = dict(tp=0, fn=0, fp=0, tn=0)
    for x in rows:
        y = int(x['label'])
        pred = float(x['score']) >= float(x['threshold'])
        assert pred == bool(int(x['prediction']))
        r[('tp' if y else 'fp') if pred else ('fn' if y else 'tn')] += 1
    r['cost'] = 5000*r['fn'] + 200*r['fp'] + 300*r['tp']
    return r


summary = read(P/'procedimientos-anidados.csv')
for item in summary:
    name = item['name'].replace(':','-')+'-'+item['policy']+'-oof.csv'
    rows = read(P/name)
    assert len(rows) == 5600 and len({r['source_row_index'] for r in rows}) == 5600
    for k,v in tally(rows).items():
        assert v == int(item[k]), (name,k)
    for r in rows:
        fold = int(r['fold'])
        assert fold in (0,1,2)

with zipfile.ZipFile(P/'metricas-por-fold.json.zip') as z:
    assert z.testzip() is None
    fold_rows = json.loads(z.read('metricas-por-fold.json'))
for rec in json.loads((P/'seleccion-solo-inner.json').read_text()):
    eligible = [x for x in fold_rows if x['fold']==rec['fold'] and x['policy']==rec['policy'] and x['category']!='rarety' and (rec['pool']=='all' or x['category']==rec['pool'])]
    key = lambda x: (0 if x['policy']=='C' or x['inner']['recall']>=.76 else 1, x['inner']['cost'],x['inner']['fn'],x['name'])
    best = min(eligible,key=key)
    assert best['name']==rec['name'] and best['threshold']==rec['threshold']

global_rows = read(P/'todas-combinaciones.csv')
assert len({x['name'] for x in global_rows})==2998
assert len(global_rows)==8934
for r in global_rows:
    parts=[x['outer'] for x in fold_rows if x['name']==r['name'] and x['policy']==r['policy']]
    for k in ('tp','fn','fp','tn','cost'):
        assert sum(x[k] for x in parts)==int(r[k])

base=next(x for x in summary if x['name']=='single:rf_reference' and x['policy']=='B')
assert [int(base[k]) for k in ('tp','fn','fp','tn','cost')]==[168,22,63,5347,173000]

spec=importlib.util.spec_from_file_location('study', HERE/'estudio.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
threshold_checks=0
for y,s in [([0,1,1,0],[.1,.1,.8,.9]),([1,0,1,0],[.5,.5,.5,.5]),([0,1,1,0,1],[0,.15,.7,1,.7])]:
    cuts=sorted(set(s))
    opts=[]
    for c in cuts:
        rows=[{'label':str(a),'score':str(b),'threshold':str(c),'prediction':str(int(b>=c))} for a,b in zip(y,s)]
        v=tally(rows)
        if v['tp']/sum(y)>=.76: opts.append((v['cost'],v['fn'],-c,c))
    assert module.threshold(y,s)==min(opts)[-1]
    threshold_checks+=1
result={'status':'passed','oof_procedures_checked':len(summary),'global_policy_rows_checked':len(global_rows),'fold_rows_checked':len(fold_rows),'selection_minima_verified':len(json.loads((P/'seleccion-solo-inner.json').read_text())),'threshold_boundary_tests':threshold_checks,'historical_rf_aviso_exact':True,'independent_arithmetic':'csv and Python integer counts; all reported procedures and aggregate configurations checked','limit':'same agent, distinct calculation path; not independent human acceptance'}
(P/'VERIFICACION.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
