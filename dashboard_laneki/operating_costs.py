"""Azken behaketa bakoitzetik kalkulatutako esku-hartze aurrekontua."""
from datetime import datetime
from decimal import Decimal
import math

OFFICIAL_COSTS = {'FN': 5000, 'FP': 200, 'TP': 300, 'TN': 0}


def classified_cost(counts):
    if any(type(counts.get(k)) is not int or counts[k] < 0 for k in OFFICIAL_COSTS):
        raise ValueError('Benetako klaseen zenbaketak behar dira')
    return sum(counts[k] * price for k, price in OFFICIAL_COSTS.items())


def official_alert_budget(machines, as_of, freshness_minutes=30.0):
    low = estimate(machines, as_of, inspection=200, critical=200,
                   freshness_minutes=freshness_minutes)
    high = estimate(machines, as_of, inspection=300, critical=300,
                    freshness_minutes=freshness_minutes)
    rows = [{'Makina': r['Makina'], 'Maila': r['Maila'], 'Behaketa': r['Behaketa'],
             'FP balitz (€)': 200, 'TP balitz (€)': 300} for r in low['rows']]
    return {**low, 'rows': rows, 'minimum': low['total'], 'maximum': high['total']}


def estimate(machines, as_of, *, inspection=200.0, critical=300.0,
             downtime_hours=0.0, hourly=1200.0, freshness_minutes=30.0):
    values = (inspection, critical, downtime_hours, hourly, freshness_minutes)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) or v < 0 for v in values) or freshness_minutes == 0:
        raise ValueError('Kostu-parametro baliogabeak')
    end = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
    if end.tzinfo is None:
        raise ValueError('UTC ebaketa behar da')
    latest = {}
    invalid = 0
    for row in machines:
        try:
            stamp = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
            if stamp.tzinfo is None or stamp > end:
                raise ValueError()
            key = row['id']
            if key not in latest or stamp > latest[key][0]:
                latest[key] = (stamp, row)
        except (KeyError, TypeError, ValueError):
            invalid += 1
    rows, stale = [], 0
    total = Decimal(0)
    for key, (stamp, row) in sorted(latest.items()):
        if (end - stamp).total_seconds() > freshness_minutes * 60:
            stale += 1
            continue
        level = row.get('alert_level')
        if level not in {'OK', 'AVISO', 'CRITICA'}:
            invalid += 1
            continue
        if level == 'OK':
            continue
        base = Decimal(str(critical if level == 'CRITICA' else inspection))
        stop = Decimal(str(downtime_hours)) * Decimal(str(hourly)) if level == 'CRITICA' else Decimal(0)
        cost = (base + stop).quantize(Decimal('0.01'))
        total += cost
        rows.append({'Makina': key, 'Maila': level, 'Behaketa': row['timestamp'],
                     'Esku-hartzea (€)': float(base), 'Geldialdi-suposizioa (€)': float(stop),
                     'Aurrekontua (€)': float(cost)})
    return {'rows': rows, 'total': float(total), 'active': len(rows),
            'stale': stale, 'invalid': invalid, 'as_of': as_of}
