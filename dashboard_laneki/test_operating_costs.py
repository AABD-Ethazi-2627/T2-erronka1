import unittest
from operating_costs import estimate, classified_cost, official_alert_budget


class CostsTests(unittest.TestCase):
    def test_official_table_and_level_independence(self):
        self.assertEqual(classified_cost(dict(TN=1150, FP=9, FN=9, TP=32)), 56400)
        result = official_alert_budget([self.row(), self.row('CRITICA', id='CNC-002')], '2026-11-12T12:01:00Z')
        self.assertEqual((result['minimum'], result['maximum']), (400, 600))
        with self.assertRaises(ValueError):
            classified_cost(dict(TN=0, FP=0, FN=-1, TP=0))
    def row(self, level='AVISO', stamp='2026-11-12T12:00:00Z', id='CNC-001'):
        return dict(id=id, alert_level=level, timestamp=stamp)

    def test_updates_and_no_double_charge(self):
        rows = [self.row(), self.row(), self.row('CRITICA', id='CNC-002')]
        result = estimate(rows, '2026-11-12T12:01:00Z', downtime_hours=2)
        self.assertEqual(result['total'], 2900)
        self.assertEqual(result['active'], 2)
        self.assertEqual(result, estimate(rows, '2026-11-12T12:01:00Z', downtime_hours=2))
        rows.append(self.row('OK', '2026-11-12T12:00:30Z'))
        self.assertEqual(estimate(rows, '2026-11-12T12:01:00Z')['active'], 1)

    def test_stale_future_unknown_empty(self):
        rows = [self.row(stamp='2026-11-12T10:00:00Z'), self.row(stamp='2026-11-12T13:00:00Z'), self.row('BAD', id='CNC-003')]
        r = estimate(rows, '2026-11-12T12:01:00Z')
        self.assertEqual((r['total'], r['stale'], r['invalid']), (0, 1, 2))
        self.assertEqual(estimate([], '2026-11-12T12:01:00Z')['total'], 0)

    def test_invalid_rates(self):
        for value in [-1, float('nan'), float('inf'), True]:
            with self.assertRaises(ValueError):
                estimate([], '2026-11-12T12:01:00Z', inspection=value)
