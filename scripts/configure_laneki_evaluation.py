"""Lotu tokiko balidazio-txostena Lanekiko modelo berari, hashak egiaztatuta."""
import hashlib
import json
from pathlib import Path
import pandas as pd


def main():
    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def write(path, value):
        Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    model = json.loads(Path('outputs/api/manifest.json').read_text())
    report = json.loads(Path('outputs/cg08/report.json').read_text())
    config_path = Path('outputs/read-config.json')
    config = json.loads(config_path.read_text())
    assert digest('outputs/api/rf.pkl') == report['model_sha256'] == config['scope']['model_artifact_sha256']
    assert digest('data/ai4i2020_train.csv') == report['source_sha256'] == model['training_source_sha256']
    frame = pd.read_csv('outputs/cg08/validation.csv', float_precision='round_trip')
    source = pd.read_csv('data/ai4i2020_train.csv')
    assert frame.source_row_index.tolist() == report['splits']['validation']
    assert frame.label.tolist() == source.loc[frame.source_row_index, 'machine_failure'].tolist()
    positive = frame.label == 1
    alert = frame.rf_score >= model['risk_threshold']
    counts = dict(tn=int((~positive & ~alert).sum()), fp=int((~positive & alert).sum()),
                  fn=int((positive & ~alert).sum()), tp=int((positive & alert).sum()))
    assert [[counts['tn'], counts['fp']], [counts['fn'], counts['tp']]] == report['validation_tuning_metrics']['confusion_matrix']
    counts.update(rows=len(frame), positives=int(positive.sum()), negatives=int((~positive).sum()), alerts=int(alert.sum()))
    provenance = dict(partition='reused_validation_for_threshold_tuning', source_sha256=report['source_sha256'],
                      validation_csv_sha256=digest('outputs/cg08/validation.csv'), report_sha256=digest('outputs/cg08/report.json'),
                      limitation='Garapen-balidazio berrerabilia; ez zuzeneko kalitatea edo test independentea.')
    path = 'outputs/api/laneki-evaluation.json'
    write(path, dict(threshold=model['risk_threshold'], overall=counts, provenance=provenance))
    proof = 'outputs/api/laneki-evaluation-binding.json'
    write(proof, dict(evaluation_sha256=digest(path), scope=config['scope'], model_version=model['model_version'], provenance=provenance))
    config['evaluation'] = dict(path='/models/laneki-evaluation.json', sha256=digest(path),
                                model_manifest_path='/models/manifest.json', model_manifest_sha256=digest('outputs/api/manifest.json'),
                                provenance_path='/models/laneki-evaluation-binding.json', provenance_sha256=digest(proof))
    backup = config_path.with_suffix('.before-evaluation.json')
    if not backup.exists():
        backup.write_bytes(config_path.read_bytes())
    write(config_path, config)
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
