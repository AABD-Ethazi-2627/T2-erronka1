"""Read-only documentation checks; no services, fitting or remote requests."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def verify():
    text = (HERE / 'MEMORIA_TEKNIKOA_EU.md').read_text()
    source = json.loads((ROOT / 'docs/rubrica/fuente.json').read_text())
    descriptors = source['descriptors']
    expected = {d['advanced_cell'] for d in descriptors}
    headings = re.findall(r'^## Zereginak!(G\d+) — ', text, re.M)
    assert len(headings) == 40 and set(headings) == expected, '40 headings required'
    for d in descriptors:
        assert '> ' + d['advanced_descriptor'] in text, d['advanced_cell']
    links = sorted(set(re.findall(r'\]\(([^)]+)\)', text)))
    for link in links:
        assert '://' not in link, f'Unexpected remote link: {link}'
        path = (HERE / link).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(), link
    manifest = json.loads((HERE / 'ITURRIAK.json').read_text())
    for path, entry in manifest['files'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == entry['sha256'], path
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == manifest['base_commit'], 'Base commit changed; reconcile sources'
    metrics = json.loads((ROOT / 'docs/evidence/CG10_results.json').read_text())['policies']
    expected_matrices = {
        '0.15': [[1147, 12], [9, 32]],
        '0.7': [[1159, 0], [14, 27]],
        '0.19082281465428477': [[1150, 9], [9, 32]],
    }
    for policy, matrix in expected_matrices.items():
        assert metrics[policy]['confusion_matrix'] == matrix
        assert sum(map(sum, matrix)) == 1200
    business = json.loads((ROOT / 'docs/evidence/CG34_20261023/business-summary.json').read_text())
    rf = business['models']['rf_reference']['B']
    assert (rf['tp'], rf['fn'], rf['fp'], rf['tn']) == (168, 22, 63, 5347)
    assert rf['cost_total_eur'] == 173000
    assert 21*5000 + 55*200 + 169*300 == 166700
    assert 4700/200 == 23.5
    # Match displayed numerical tables too, not just the source JSON.
    for row in [
        '| AVISO, ≥0,15 | 32 | 9 | 12 | 1.147 | %78,05 | %72,73 |',
        '| CRITICA, ≥0,70 | 27 | 14 | 0 | 1.159 | %65,85 | %100,00 |',
        '| F2 esploratzailea, ≥0,19082281465428477 | 32 | 9 | 9 | 1.150 | %78,05 | %78,05 |',
        '| batch32-base-1 | 600/600 | 14,958 | 82,747 | 340/0 |',
        '| batch32-base-2 | 600/600 | 15,116 | 83,859 | 340/0 |',
        '| batch32-base-3 | 600/600 | 14,365 | 78,135 | 340/0 |',
    ]:
        assert row in text, row
    for required in ['AI4I_CURRENT_STATE_ONLY', 'temporal_prediction_enabled=false',
                     'A03', 'A04', 'A07', '503', '409', '422', '4.700',
                     'historikoki probatua', 'ez du lege-irizpen berririk']:
        assert required in text, required
    return {
        'status': 'passed', 'criteria': len(headings),
        'literal_descriptors': len(descriptors), 'local_targets': len(links),
        'source_hashes': len(manifest['files']), 'word_count': len(text.split()),
        'numerical_checks': 'CG10 matrices, RF B cost/counts, pair cost, marginal cost; displayed metrics/load rows',
        'limits': 'Documentation checks only; no model training, live integration, current CI, legal revalidation or human acceptance.',
    }


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
