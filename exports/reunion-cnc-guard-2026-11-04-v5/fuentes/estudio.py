"""Offline extension of sealed CG34 scores. No base pickle loading or serving changes.

Run from repository root: OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
MKL_NUM_THREADS=1 .venv/bin/python exports/estudio-multimodelo-2026-11-04/estudio.py
Outputs are append-only: choose a new --output for another execution.
"""

import argparse
import csv
import hashlib
import io
import itertools
import json
import platform
import time
import warnings
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False))


def threshold(y, s):
    """Minimize official marginal cost; >= comparisons and complete score ties."""
    y, s = np.asarray(y, dtype=int), np.asarray(s, dtype=float)
    if not np.isfinite(s).all() or not y.sum():
        raise ValueError("Finite scores and positive support required")
    order = np.argsort(-s, kind="stable")
    ends = np.r_[np.flatnonzero(np.diff(s[order])), len(s) - 1]
    tp = np.cumsum(y[order])[ends]
    fp = np.cumsum(1 - y[order])[ends]
    fn = y.sum() - tp
    eligible = np.flatnonzero(tp / y.sum() >= 0.76)
    best = min(eligible, key=lambda k: (200 * fp[k] + 4700 * fn[k], fn[k], -s[order[ends[k]]]))
    return float(s[order[ends[best]]])


def counts(y, s, cut):
    pred = np.asarray(s) >= cut
    y = np.asarray(y)
    tp, fp = int(np.sum(pred & (y == 1))), int(np.sum(pred & (y == 0)))
    fn, tn = int(np.sum(~pred & (y == 1))), int(np.sum(~pred & (y == 0)))
    return dict(n=len(y), positives=int(y.sum()), tp=tp, fp=fp, fn=fn, tn=tn,
                recall=tp / max(tp + fn, 1), precision=tp / max(tp + fp, 1),
                f1=2 * tp / max(2 * tp + fp + fn, 1),
                f2=5 * tp / max(5 * tp + fp + 4 * fn, 1),
                cost=5000 * fn + 200 * fp + 300 * tp,
                cost_per_1000=(5000 * fn + 200 * fp + 300 * tp) * 1000 / len(y))


def rank(m, name):
    return m['cost'], m['fn'], name


def load_archive(path, manifest, train):
    result = defaultdict(list)
    verified = []
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError("ZIP CRC mismatch")
        if sha(z.read('manifest.json')) != sha((ROOT / 'docs/evidence/CG34_20261023/manifest.json').read_bytes()):
            raise ValueError("Manifest mismatch")
        for n in z.namelist():
            if not n.startswith('units/') or not n.endswith('/task.json'):
                continue
            raw_task = z.read(n)
            task = json.loads(raw_task)
            if task['phase'] not in ('inner', 'outer'):
                continue
            prefix = n[:-len('task.json')]
            res_raw, account_raw = z.read(prefix + 'result.json'), z.read(prefix + 'accounting.json')
            res, account = json.loads(res_raw), json.loads(account_raw)
            if res['status'] != 'complete' or account['status'] != 'complete':
                raise ValueError("Incomplete source unit")
            b = z.read(prefix + 'scores.csv')
            if sha(raw_task) != res['task_sha256'] or sha(b) != res['scores_sha256']:
                raise ValueError("Source unit hash mismatch")
            fit, held = set(task['fit']), set(task['held'])
            if fit & held or not (fit | held) <= set(train.index):
                raise ValueError("Forbidden row or fit/held overlap")
            phase, fold = task['phase'], task['fold']
            outer = fold[0] if phase == 'inner' else fold
            expected = manifest['outer'][outer]
            if phase == 'inner':
                expected = expected['inner'][fold[1]]
            if task['fit'] != expected['fit'] or task['held'] != expected['held']:
                raise ValueError("Fold provenance mismatch")
            frame = pd.read_csv(io.BytesIO(b), float_precision='round_trip')
            if frame.source_row_index.tolist() != task['held']:
                raise ValueError("Score order mismatch")
            frame = frame.set_index('source_row_index')
            if not np.array_equal(frame.label.to_numpy(), train.loc[frame.index, 'machine_failure']):
                raise ValueError("Labels do not match source")
            if task['model'].startswith('xgb_'):
                frame['score'] = frame.score.to_numpy().astype(np.float32).astype(float)
            if not np.isfinite(frame.score).all():
                raise ValueError("Nonfinite scores")
            result[(outer, phase, task['model'])].append(frame)
            verified.append({'unit': prefix, 'task_sha256': sha(raw_task), 'result_sha256': sha(res_raw), 'scores_sha256': sha(b)})
    matrices = {}
    names = [s['name'] for s in manifest['catalog']]
    for outer in range(3):
        for phase in ('inner', 'outer'):
            ids = manifest['outer'][outer]['fit' if phase == 'inner' else 'held']
            columns = []
            for name in names:
                parts = result[(outer, phase, name)]
                if len(parts) != (3 if phase == 'inner' else 1):
                    raise ValueError("Incomplete model coverage")
                frame = pd.concat(parts)
                if frame.index.duplicated().any() or set(frame.index) != set(ids):
                    raise ValueError("OOF coverage mismatch")
                columns.append(frame.loc[ids, 'score'].to_numpy())
            matrices[(outer, phase)] = np.column_stack(columns)
    return matrices, verified


def profile(train, manifest):
    predictors = ['air_temp_K', 'process_temp_K', 'rpm', 'torque_Nm', 'tool_wear_min', 'machine_type']
    sensors = predictors[:-1]
    derived = pd.DataFrame({'temp_diff': train.process_temp_K - train.air_temp_K,
                            'power_W': train.rpm * train.torque_Nm * 2 * np.pi / 60,
                            'wear_torque': train.tool_wear_min * train.torque_Nm})
    return {'rows': len(train), 'positives': int(train.machine_failure.sum()),
            'negative_rows': int((train.machine_failure == 0).sum()),
            'columns': train.columns.tolist(), 'allowed_inputs': predictors,
            'excluded_columns': [c for c in train.columns if c not in predictors + ['machine_failure']],
            'nulls': {k: int(v) for k, v in train.isna().sum().items()},
            'duplicate_predictor_rows': int(train[predictors].duplicated().sum()),
            'nonfinite_sensor_cells': int((~np.isfinite(train[sensors].to_numpy(float))).sum()),
            'sensor_ranges': {c: {'min': float(train[c].min()), 'max': float(train[c].max()), 'unit': 'K' if c.endswith('_K') else 'RPM' if c == 'rpm' else 'Nm' if c == 'torque_Nm' else 'min'} for c in sensors},
            'type_support': {str(k): {'n': int(len(g)), 'positives': int(g.machine_failure.sum())} for k, g in train.groupby('machine_type')},
            'derived': {c: {'min': float(derived[c].min()), 'max': float(derived[c].max())} for c in derived},
            'forbidden_features': 'row/product/machine IDs, timestamps without valid history, target, failure subtypes, post-outcome columns; never used by new meta-models',
            'time_and_entity_limit': 'Rows are snapshots from approved tabular source. No physical chronological trajectory is established by an ID or repeated playback.',
            'membership_sizes': {k: len(v) for k, v in manifest['membership'].items()}}


def run(output):
    begin = time.perf_counter()
    output.mkdir(exist_ok=False, parents=True)
    protocol = json.loads((HERE / 'protocol.json').read_text())
    write(output / 'protocol.json', protocol)
    source = ROOT / 'data/ai4i2020_train.csv'
    manifest = json.loads((ROOT / 'docs/evidence/CG34_20261023/manifest.json').read_text())
    if sha(source.read_bytes()) != manifest['source_sha256']:
        raise ValueError("Wrong source")
    data = pd.read_csv(source, float_precision='round_trip')
    members = manifest['membership']
    assert len(data) == 8000 and len(members['train']) == 5600
    assert set().union(*map(set, members.values())) == set(range(8000))
    assert sum(map(len, members.values())) == 8000
    train = data.loc[members['train']].copy()
    del data
    write(output / 'calidad-datos.json', profile(train, manifest))
    archive = ROOT / protocol['source_archive']
    if sha(archive.read_bytes()) != protocol['archive_sha256']:
        raise ValueError("Source archive mismatch")
    matrices, verified = load_archive(archive, manifest, train)
    write(output / 'unidades-verificadas.json', verified)
    specs = manifest['catalog']
    supervised = [i for i, s in enumerate(specs) if not s['anomaly']]
    anomaly = [i for i, s in enumerate(specs) if s['anomaly']]
    families = sorted({specs[i]['family'] for i in supervised if specs[i]['family'] != 'dummy'})
    pairs = [(a, b, w) for a, b in itertools.combinations(supervised, 2) for w in (.25, .5, .75)]
    triples = list(itertools.combinations(families, 3))
    all_predictions = defaultdict(list)
    summaries = defaultdict(list)
    selections, fold_records, warning_log = [], [], []
    reference_name = 'single:rf_reference'
    policy_names = ('A', 'B', 'C')
    for fold in range(3):
        ids_i, ids_o = manifest['outer'][fold]['fit'], manifest['outer'][fold]['held']
        yi, yo = train.loc[ids_i, 'machine_failure'].to_numpy(), train.loc[ids_o, 'machine_failure'].to_numpy()
        mi, mo = matrices[(fold, 'inner')], matrices[(fold, 'outer')]
        inner_rank = []
        for i in supervised:
            c = .5 if specs[i]['family'] == 'dummy' else threshold(yi, mi[:, i])
            m = counts(yi, mi[:, i], c)
            inner_rank.append((rank(m, specs[i]['name']), i))
        ordered = [i for _, i in sorted(inner_rank)]
        family_best = {f: next(i for i in ordered if specs[i]['family'] == f) for f in families}
        best = {}
        def evaluate(name, category, si, so, members_used, force_a=None, diagnostic=False):
            cuts = {'A': threshold(yi, si) if force_a is None else force_a, 'B': .15, 'C': .70}
            for policy in policy_names:
                if diagnostic and policy != 'A':
                    continue
                cut = cuts[policy]
                inside, outside = counts(yi, si, cut), counts(yo, so, cut)
                summaries[(name, category, policy)].append((fold, outside))
                fold_records.append(dict(fold=fold, name=name, category=category, policy=policy, threshold=cut, members=members_used, inner=inside, outer=outside))
                for pool in ('all', category):
                    if diagnostic and pool == 'all':
                        continue
                    key = policy, pool
                    # AVISO is selected among inner candidates meeting recall floor.
                    eligibility = 0 if policy == 'C' or inside['recall'] >= .76 else 1
                    score = (eligibility, *rank(inside, name))
                    if key not in best or score < best[key]['rank']:
                        best[key] = dict(rank=score, name=name, category=category, threshold=cut,
                                         inner=inside, score=so.copy(), members=members_used)
                if name == reference_name:
                    all_predictions[(reference_name, policy)].append((fold, ids_o, so.copy(), cut))
        for i in supervised:
            evaluate('single:' + specs[i]['name'], 'single', mi[:, i], mo[:, i], [specs[i]['name']], .5 if specs[i]['family'] == 'dummy' else None)
        for a, b, w in pairs:
            evaluate(f'pair:{specs[a]["name"]}+{specs[b]["name"]}@{w}', 'pair', w * mi[:, a] + (1-w) * mi[:, b], w * mo[:, a] + (1-w) * mo[:, b], [specs[a]['name'], specs[b]['name']])
        for fams in triples:
            ix = [family_best[f] for f in fams]
            evaluate('triple:' + '+'.join(fams), 'triple', mi[:, ix].mean(axis=1), mo[:, ix].mean(axis=1), [specs[i]['name'] for i in ix])
        non_dummy = [i for i in ordered if specs[i]['family'] != 'dummy']
        for k in (2, 3, 5, 8, 16):
            ix = non_dummy[:k]
            for method in ('equal', 'rank'):
                w = np.ones(k) if method == 'equal' else 1 / np.arange(1, k+1)
                evaluate(f'committee:top{k}:{method}', 'committee', np.average(mi[:, ix], axis=1, weights=w), np.average(mo[:, ix], axis=1, weights=w), [specs[i]['name'] for i in ix])
        for k in (3, 5, 8):
            ix = non_dummy[:k]
            for C, balanced in itertools.product((.1, 1., 10.), (False, True)):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    meta = LogisticRegression(C=C, class_weight='balanced' if balanced else None, max_iter=3000, solver='lbfgs', random_state=42).fit(mi[:, ix], yi)
                warning_log.extend({'fold': fold, 'model': f'stack{k}:{C}:{balanced}', 'message': str(w.message)} for w in caught)
                evaluate(f'stack:top{k}:C{C}:balanced{balanced}', 'stack', meta.predict_proba(mi[:, ix])[:, 1], meta.predict_proba(mo[:, ix])[:, 1], [specs[i]['name'] for i in ix])
        rf = next(i for i, s in enumerate(specs) if s['name'] == 'rf_reference')
        for i in anomaly:
            for alpha in (.01, .03, .05):
                # Tail on inner negative proxy; not a failure probability or true anomaly label.
                cut = float(np.quantile(mi[yi == 0, i], 1-alpha, method='higher'))
                si = ((mi[:, rf] >= .15) | (mi[:, i] >= cut)).astype(float)
                so = ((mo[:, rf] >= .15) | (mo[:, i] >= cut)).astype(float)
                evaluate(f'rarety-union:{specs[i]["name"]}:tail{alpha}', 'rarety', si, so, ['rf_reference', specs[i]['name']], force_a=.5, diagnostic=True)
        for (policy, pool), rec in best.items():
            if pool == 'rarety':
                continue
            procedure = 'selector:' + pool
            all_predictions[(procedure, policy)].append((fold, ids_o, rec['score'], rec['threshold']))
            selections.append(dict(fold=fold, policy=policy, pool=pool, name=rec['name'], members=rec['members'], threshold=rec['threshold'], inner=rec['inner']))
        print(f'outer {fold}: {len(best)} selectors; configurations {len(summaries)} policy rows', flush=True)
    leaderboard = []
    for (name, cat, policy), records in summaries.items():
        assert len(records) == 3
        n, tp, fn, fp, tn = (sum(r[k] for _, r in records) for k in ('n', 'tp', 'fn', 'fp', 'tn'))
        assert n == 5600 and tp + fn == 190 and tp + fp + fn + tn == n
        cost = 5000 * fn + 200 * fp + 300 * tp
        leaderboard.append(dict(name=name, category=cat, policy=policy, n=n, tp=tp, fn=fn, fp=fp, tn=tn,
                                recall=tp/190, precision=tp/max(tp+fp, 1), cost=cost, cost_per_1000=cost*1000/n))
    pd.DataFrame(leaderboard).sort_values(['policy', 'cost', 'fn', 'name']).to_csv(output/'todas-combinaciones.csv', index=False)
    with zipfile.ZipFile(output/'metricas-por-fold.json.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('metricas-por-fold.json', json.dumps(fold_records, allow_nan=False))
    procedures = []
    for (name, policy), chunks in all_predictions.items():
        frames = [pd.DataFrame({'source_row_index': ids, 'fold': fold, 'label': train.loc[ids, 'machine_failure'].to_numpy(), 'score': score, 'threshold': cut, 'prediction': (score >= cut).astype(int)}) for fold, ids, score, cut in chunks]
        frame = pd.concat(frames).sort_values('source_row_index')
        assert len(frame) == 5600 and not frame.source_row_index.duplicated().any()
        y, s = frame.label.to_numpy(), frame.score.to_numpy()
        m = counts(y, s, frame.threshold.to_numpy())
        m.update(name=name, policy=policy, average_precision=float(average_precision_score(y, s)),
                 roc_auc=float(roc_auc_score(y, s)), brier=float(brier_score_loss(y, s)))
        procedures.append(m)
        frame.to_csv(output/(name.replace(':','-')+'-'+policy+'-oof.csv'), index=False, float_format='%.17g')
    pd.DataFrame(procedures).to_csv(output/'procedimientos-anidados.csv',index=False)
    write(output/'seleccion-solo-inner.json',selections)
    write(output/'advertencias.json',warning_log)
    write(output/'ejecucion.json',dict(source_sha256=manifest['source_sha256'], archive_sha256=sha(archive.read_bytes()),
          protocol_sha256=sha((HERE/'protocol.json').read_bytes()), code_sha256=sha(Path(__file__).read_bytes()),
          python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__, pandas=pd.__version__,
          base_configurations=len(supervised), anomaly_configurations=len(anomaly), pairs=len(pairs), family_triples=len(triples),
          committees=10, stacking_configurations=18, new_meta_fits=54, rarety_unions=30,
          configurations_per_outer=40+len(pairs)+len(triples)+10+18+30,
          verified_source_units=len(verified), wall_seconds=time.perf_counter()-begin,
          no_base_refits=True, no_served_changes=True, no_validation_or_test_scoring=True,
          caveats=['All folds historically explored; post-hoc development evidence, not independent final test.',
                   'Family/top-k/member and policy selection excludes outer-held labels in this execution.',
                   'Stack base inputs OOF; meta threshold learned on meta training outputs, so internal stacking estimates are optimistic. Outer metrics evaluate that procedure.',
                   'Fixed .15/.70 applied for comparison, not claimed calibrated or interchangeable across models.',
                   'No measured runtime latency of a fitted ensemble serving package; no model deployed.',
                   'Raw anomaly scores never averaged as probabilities; union is a separate normality-proxy diagnostic.']))
    print(pd.DataFrame(procedures).query("policy == 'A'")[['name','fn','fp','recall','cost_per_1000']].to_string(index=False),flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=HERE/'run-01')
    args=ap.parse_args()
    with threadpool_limits(limits=1):
        run(args.output)
