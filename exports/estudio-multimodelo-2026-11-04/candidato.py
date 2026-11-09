"""Research-only CART/LightGBM candidate, separate from the serving API.

From repository root, with the research numerical dependencies available:
  .venv/bin/python exports/estudio-multimodelo-2026-11-04/candidato.py fit
  .venv/bin/python exports/estudio-multimodelo-2026-11-04/candidato.py predict --input six-inputs.csv --output new-output.json

Only load this project's own hash-verified bundle; joblib is not a safe format
for arbitrary third-party data. Nothing here changes MODEL_MANIFEST or the API.
"""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from scripts.ml_study_models import StudyModel

INPUTS = ['air_temp_K','process_temp_K','rpm','torque_Nm','tool_wear_min','machine_type']
PACKAGES = ['numpy','pandas','scipy','scikit-learn','joblib','lightgbm']


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,obj):
    with path.open('x') as f: json.dump(obj,f,indent=2,allow_nan=False)


def validate(frame):
    if set(frame.columns) != set(INPUTS):
        raise ValueError('Exactly six original inputs required; labels/IDs/failure types forbidden')
    if frame.empty or len(frame)>10000:
        raise ValueError('Require 1–10000 rows')
    numeric=frame[INPUTS[:-1]].to_numpy(float)
    if not np.isfinite(numeric).all() or (numeric<0).any():
        raise ValueError('Finite nonnegative sensors required')
    if not set(frame.machine_type)<=set('HML'):
        raise ValueError('Known machine types H/M/L required')


def scores(models,weights,frame):
    validate(frame)
    individual=np.column_stack([model.score(frame[INPUTS]) for model in models])
    if not np.isfinite(individual).all() or (individual<0).any() or (individual>1).any():
        raise ValueError('Invalid model output')
    return individual@np.asarray(weights),individual


def fit(bundle):
    bundle.mkdir(parents=True,exist_ok=False)
    source=ROOT/'data/ai4i2020_train.csv'
    old=json.loads((ROOT/'docs/evidence/CG34_20261023/manifest.json').read_text())
    assert sha(source)==old['source_sha256']
    selection=json.loads((HERE/'run-01/seleccion-fija-screening.json').read_text())
    winner=selection['winner']
    assert (winner['a'],winner['b'],winner['weight_a'])==('cart_depth3','lgb_7_True',.75)
    frame=pd.read_csv(source,float_precision='round_trip').loc[old['membership']['train']]
    catalog={s['name']:s for s in old['catalog']}
    begin=time.perf_counter()
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter('always')
        models=[StudyModel(catalog[name]).fit(frame[INPUTS],frame.machine_failure.to_numpy()) for name in (winner['a'],winner['b'])]
    weights=[.75,.25]
    sample=frame[INPUTS].iloc[:32]
    before,individual=scores(models,weights,sample)
    joblib.dump({'models':models,'weights':weights},bundle/'ensemble.joblib')
    # Own in-process artifact, immediately reloaded under the same environment.
    restored=joblib.load(bundle/'ensemble.joblib')
    after,_=scores(restored['models'],restored['weights'],sample)
    assert np.array_equal(before,after)
    tests=0
    for invalid in [sample.assign(machine_failure=0),sample.assign(machine_type='X'),sample.assign(rpm=np.nan),sample.assign(torque_Nm=-1)]:
        try: validate(invalid)
        except ValueError: tests+=1
        else: raise AssertionError('Invalid inputs accepted')
    sample.to_csv(bundle/'ejemplo-seis-entradas.csv',index=False,float_format='%.17g')
    versions={p:importlib.metadata.version(p) for p in PACKAGES}
    refs=['scripts/ml_study_models.py','scoring/preparation.py','scoring/scope.py']
    meta={'scope':'AI4I_CURRENT_STATE_ONLY','status':'research candidate fitted; not served or independently validated',
          'members':[winner['a'],winner['b']],'weights':weights,'inputs':INPUTS,'python':platform.python_version(),'versions':versions,
          'source_sha256':sha(source),'train_rows':len(frame),'train_positives':int(frame.machine_failure.sum()),
          'train_index_sha256':hashlib.sha256(json.dumps(frame.index.tolist(),separators=(',',':')).encode()).hexdigest(),
          'code':{name:sha(ROOT/name) for name in refs},'runner_sha256':sha(Path(__file__)),
          'model_sha256':sha(bundle/'ensemble.joblib'),'selection_sha256':sha(HERE/'run-01/seleccion-fija-screening.json'),
          'selection':'Minimum cost among 2340 pairs on historical screening OOF train; not chosen from outer results.',
          'policies':{'research_review':.15,'research_critical':.70},
          'sensor_support':{c:{'min':float(frame[c].min()),'max':float(frame[c].max())} for c in INPUTS[:-1]},
          'fit_and_reload_wall_seconds':time.perf_counter()-begin,'reload_max_abs_difference':float(np.max(np.abs(before-after))),
          'invalid_input_tests':tests,'warnings':[str(w.message) for w in recorded],
          'limits':['Refit in recorded local versions, distinct from original historical fitted artifacts.',
                    'No evaluation on validation or excluded test. Example predictions are training rows, not performance evidence.',
                    'Weighted score is uncalibrated current-state evidence, no future failure probability, ETA or RUL.',
                    'No serving API, policy, model or runtime environment was modified.',
                    'No integrated inference latency, external data or human acceptance is demonstrated.']}
    save(bundle/'manifest.json',meta)
    (bundle/'requirements-candidato.txt').write_text(''.join(p+'=='+v+'\n' for p,v in versions.items()))
    print(json.dumps({'members':meta['members'],'versions':versions,'reload_exact':True,'invalid_input_tests':tests,'fit_seconds':meta['fit_and_reload_wall_seconds']}))


def predict(bundle,input_file,output):
    meta=json.loads((bundle/'manifest.json').read_text())
    if sha(bundle/'ensemble.joblib')!=meta['model_sha256'] or sha(Path(__file__))!=meta['runner_sha256']:
        raise ValueError('Candidate artifact/runner hash mismatch')
    for name,expected in meta['code'].items():
        if sha(ROOT/name)!=expected: raise ValueError('Candidate source code mismatch')
    for name,version in meta['versions'].items():
        if importlib.metadata.version(name)!=version: raise ValueError('Candidate numerical environment mismatch: '+name)
    data=pd.read_csv(input_file,float_precision='round_trip')
    validate(data)
    own=joblib.load(bundle/'ensemble.joblib')
    score,individual=scores(own['models'],own['weights'],data)
    out=[]
    for i,s in enumerate(score):
        outside=[c for c,r in meta['sensor_support'].items() if not r['min']<=float(data.iloc[i][c])<=r['max']]
        out.append({'row_position':i,'research_current_failure_score':float(s),
                    'member_scores':{n:float(v) for n,v in zip(meta['members'],individual[i])},
                    'research_review_ge_015':bool(s>=.15),'research_alert_level':'CRITICA' if s>=.70 else 'AVISO' if s>=.15 else 'OK',
                    'outside_training_sensor_support':outside})
    save(output,{'scope':meta['scope'],'model_sha256':meta['model_sha256'],'score_semantics':'uncalibrated current-state score; research only',
                 'temporal_prediction_enabled':False,'rows':out,'limits':meta['limits']})
    print('Research predictions written:',len(out))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['fit','predict'])
    ap.add_argument('--bundle',type=Path,default=HERE/'candidato')
    ap.add_argument('--input',type=Path)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    with threadpool_limits(limits=1):
        if args.command=='fit':fit(args.bundle)
        else:
            if not args.input or not args.output:ap.error('predict requires --input and --output')
            predict(args.bundle,args.input,args.output)
