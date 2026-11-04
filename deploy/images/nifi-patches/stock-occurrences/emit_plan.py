"""Emit writer-shaped plans, unapproved by default; never patches an archive.

After external QA, the parent can supply an explicit hash-bound review record.
This record is an auditable assertion by the caller, not automated QA evidence.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import map_candidates as mapping


def emit(candidate_path, families, approval=None):
    candidate = mapping.load(candidate_path)
    if not families or set(families) - set(mapping.PAIRS):
        raise ValueError('explicit known families required')
    selected = [t for t in candidate['targets'] if t['family'] in families]
    if not selected or any(t['status'] != 'candidate-pending-parent-QA' for t in selected):
        raise ValueError('missing/blocked family; no executable plan')
    for f in families:
        ts = [t for t in selected if t['family'] == f]
        if not ts or len(ts) != candidate['counts'][f] or any(t['expected_occurrences'] != len(ts) for t in ts):
            raise ValueError('incomplete occurrence mapping')
    status = 'candidate-pending-parent-QA'
    if approval is not None:
        review = mapping.load(approval)
        if (set(review) != {'candidate_sha256', 'families', 'decision', 'review_reference'}
                or review['candidate_sha256'] != mapping.writer.digest(candidate_path)
                or sorted(review['families']) != sorted(set(families))
                or review['decision'] != 'approved'
                or not isinstance(review['review_reference'], str) or not review['review_reference'].strip()):
            raise ValueError('missing/drifted/invalid review record')
        status = 'approved-exact-occurrence'
    targets = []
    for t in selected:
        if (not t['chain_sha256'] or t['chain_sha256'][-1] in mapping.writer.BLOCKED_INPUTS
                or not isinstance(t['replacement'], str)
                or mapping.writer.digest(t['replacement']) != t['replacement_sha256']):
            raise ValueError('null/blocked/drifted replacement')
        targets.append({k: t[k] for k in ('outer', 'members', 'chain_sha256', 'replacement', 'replacement_sha256', 'expected_occurrences')} | {'status': status})
    return {'schema': 1, 'inventory_sha256': candidate['inventory_sha256'], 'targets': targets}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate', type=Path)
    p.add_argument('--families', nargs='+', required=True, choices=sorted(mapping.PAIRS))
    p.add_argument('--review-record', type=Path)
    a = p.parse_args()
    print(json.dumps(emit(a.candidate, a.families, a.review_record), indent=2, sort_keys=True))
