import copy
import unittest

from domain import (
    demo_machines,
    gallery_machine,
    kpis,
    load_machines,
    selected_machine,
    validate_machines,
)


class SnapshotTests(unittest.TestCase):
    def test_gallery_does_not_rewrite_source_state_or_measurements(self):
        source = demo_machines()
        previous = copy.deepcopy(source)
        for row in source:
            decorated = gallery_machine(row)
            for key, value in row.items():
                self.assertEqual(decorated[key], value)
        self.assertEqual(source, previous)
        self.assertEqual(
            sum(gallery_machine(m)["egoera_mota"] == "Larria" for m in source),
            kpis(source)["akatsak"],
        )

    def test_api_failure_and_partial_snapshot_never_generate_demo(self):
        machines, status = load_machines("api", lambda _: None)
        self.assertEqual((machines, status), ([], "degraded"))
        partial = demo_machines()[8:10]
        self.assertEqual(load_machines("api", lambda _: partial), (partial, "api"))
        self.assertEqual(kpis(partial)["guztira"], 2)

    def test_explicit_demo_never_calls_api(self):
        def reject(_):
            raise AssertionError("Demo must not query an API")

        self.assertEqual(load_machines("demo", reject), (demo_machines(), "demo"))

    def test_malformed_state_degrades_instead_of_crashing(self):
        for state in ([], {}, None, 1):
            with self.subTest(state=state):
                snapshot = [{**demo_machines()[0], "egoera": state}]
                self.assertEqual(
                    load_machines("api", lambda _, snapshot=snapshot: snapshot),
                    ([], "degraded"),
                )

    def test_malformed_snapshots_are_rejected(self):
        good = demo_machines()[0]
        for key, value in [
            ("id", "<script>"),
            ("zenbakia", 99),
            ("zenbakia", True),
            ("egoera", "Unknown"),
            ("rpm", float("nan")),
            ("rpm", True),
            ("rpm", 10**500),
            ("torque", -1),
        ]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_machines([{**good, key: value}])
        for rows in ([], [good, good], None, [None]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_machines(rows)

    def test_changed_deep_link_and_user_selection_survive_reruns(self):
        rows = demo_machines()
        self.assertEqual(selected_machine(None, "CNC-004", rows), "CNC-004")
        self.assertEqual(
            selected_machine("CNC-009", "CNC-004", rows, "CNC-004"), "CNC-009"
        )
        self.assertEqual(
            selected_machine("CNC-009", "CNC-017", rows, "CNC-004"), "CNC-017"
        )
        self.assertEqual(selected_machine("INVALID", "INVALID", rows), "CNC-001")
        self.assertIsNone(selected_machine(None, None, []))

    def test_maintenance_and_health_are_not_fabricated(self):
        row = gallery_machine(demo_machines()[3])
        self.assertEqual(row["tenperatura"], 36.3)
        self.assertEqual(row["kokapena"], "A lerroa · 4. kokapena")
        self.assertEqual(row["geldialdiaren_iraupena"], "Ez dago daturik")
        self.assertIsNone(kpis(demo_machines())["osasuna"])


if __name__ == "__main__":
    unittest.main()
