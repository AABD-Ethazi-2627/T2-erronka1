"""Streamlit regression checks; no API server or industrial connection required."""

import ast
import os
import unittest
from pathlib import Path
from types import CodeType, FunctionType
from unittest.mock import Mock, patch

import requests
import streamlit as st
from domain import demo_machines
from streamlit.testing.v1 import AppTest, app_test


def tearDownModule():
    # AppTest owns a global temporary directory, which must be closed explicitly
    # when testing with ResourceWarning promoted to errors.
    app_test.TMP_DIR.cleanup()


class AppTests(unittest.TestCase):
    def test_timer_requests_full_rerun_only_outside_inline_render(self):
        # Execute the real control body with UI/time doubles. AppTest alone runs
        # fragments inline and cannot exercise their independent timer context.
        tree = ast.parse(Path(__file__).with_name("app.py").read_text())
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "live_refresh_control"
        )
        function.decorator_list = []
        code = compile(
            ast.Module(body=[function], type_ignores=[]), "live_refresh_control", "exec"
        )
        for inline in (True, False):
            with self.subTest(inline=inline):
                ui = Mock()
                ui.session_state = {"live_last_refresh": 0, "live_inline": inline}
                ui.toggle.return_value = True
                refresh = Mock()
                namespace = {
                    "st": ui,
                    "time": Mock(monotonic=Mock(return_value=6)),
                    "refresh_reads": refresh,
                }
                body = next(
                    value for value in code.co_consts if isinstance(value, CodeType)
                )
                FunctionType(body, namespace)()
                refresh.assert_called_once_with()
                if inline:
                    ui.rerun.assert_not_called()
                else:
                    ui.rerun.assert_called_once_with(scope="app")

    def setUp(self):
        self.environment = patch.dict(os.environ, {"LANEKI_MODE": "demo"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        st.cache_data.clear()

    def app(self):
        return AppTest.from_file(
            str(Path(__file__).with_name("app.py")), default_timeout=30
        )

    def assert_clean(self, app):
        self.assertEqual(list(app.exception), [])

    def test_pages_show_demo_and_do_not_call_api(self):
        with patch("requests.get", side_effect=AssertionError("Demo queried API")):
            app = self.app().run()
            self.assert_clean(app)
            for page in ("Makinak", "Datuak", "Abisuak", "Ezarpenak"):
                if page == "Ezarpenak":
                    app.query_params["orria"] = page
                    app.run()
                else:
                    app.button(key=f"nav_{page}").click().run()
                self.assert_clean(app)
                self.assertTrue(any("DEMO" in warning.value for warning in app.warning))

    def test_url_selection_changes_with_map_and_survives_rerun(self):
        app = self.app()
        app.query_params["makina"] = "CNC-004"
        app.run()
        self.assert_clean(app)
        app.button(key="machine_button_9").click().run()
        self.assert_clean(app)
        self.assertEqual(app.session_state["hautatutako_makina"], "CNC-009")
        self.assertEqual(app.query_params["makina"], "CNC-009")
        app.run()
        self.assertEqual(app.session_state["hautatutako_makina"], "CNC-009")
        app.query_params["makina"] = "INVALID"
        app.run()
        self.assert_clean(app)
        self.assertNotEqual(app.session_state["hautatutako_makina"], "INVALID")

    def test_partial_api_keeps_only_real_rows(self):
        os.environ["LANEKI_MODE"] = "api"
        response = Mock()
        response.json.return_value = demo_machines()[8:10]
        with patch("requests.get", return_value=response):
            app = self.app().run()
            self.assert_clean(app)
            buttons = [
                button
                for button in app.button
                if (button.key or "").startswith("machine_button_")
            ]
            self.assertEqual(len(buttons), 2)
            self.assertEqual(app.session_state["hautatutako_makina"], "CNC-009")

    def test_api_outage_shows_error_without_demo(self):
        os.environ["LANEKI_MODE"] = "api"
        with patch("requests.get", side_effect=requests.ConnectionError("offline")):
            app = self.app().run()
            self.assert_clean(app)
            self.assertTrue(app.error)
            self.assertIn("Ez da demo-daturik", app.error[0].value)
            self.assertFalse(
                any(
                    (button.key or "").startswith("machine_button_")
                    for button in app.button
                )
            )


class CanonicalAppTests(unittest.TestCase):
    """Assert displayed values, not just absence of Streamlit exceptions."""

    setUp = AppTests.setUp
    app = AppTests.app
    assert_clean = AppTests.assert_clean

    def api(self, rows, history_payload=None, evaluation_payload=None):
        from test_read_contracts import history_fixture

        os.environ["LANEKI_MODE"] = "api"
        os.environ["LANEKI_API_URL"] = "http://127.0.0.1:18271/api"
        self.addCleanup(os.environ.pop, "LANEKI_API_URL", None)
        payload = history_payload or history_fixture()

        self.calls = []

        def get(url, **kwargs):
            self.calls.append((url, kwargs))
            if getattr(self, "api_down", False):
                raise requests.ConnectionError("fixture API outage")
            self.assertTrue(url.startswith("http://127.0.0.1:18271/api/"))
            if url.endswith("/makinak"):
                data = rows
            elif url.endswith("/periodoak"):
                data = {key: payload for key in ("astea", "hilabetea", "sei_hilabete")}
            elif url.endswith("/model-evaluation"):
                data = evaluation_payload or {"available": False}
            elif url.endswith("/kpis"):
                data = {"metadata": {"coverage": 1}, "osasuna": None}
            else:
                data = payload
            response = Mock()
            response.json.return_value = data
            return response

        patcher = patch("requests.get", side_effect=get)
        patcher.start()
        self.addCleanup(patcher.stop)
        return self.app()

    def assert_sentinel(self, app):
        self.assert_clean(app)
        readings = {(m.label, m.value) for m in app.metric}
        for pair in (
            ("Prozesu-tenperatura (°C)", "21"),
            ("Abiadura (RPM)", "1801"),
            ("Bihurdura-momentua (Nm)", "5"),
            ("Erremintaren higadura (min)", "7"),
        ):
            self.assertIn(pair, readings)
        self.assertTrue(any("Normala" in m.value for m in app.markdown))

    def test_sentinel_all_pages_and_modal(self):
        from test_read_contracts import SENTINEL

        app = self.api([SENTINEL]).run()
        self.assert_sentinel(app)
        for page in ("Makinak", "Datuak", "Abisuak"):
            app.button(key=f"nav_{page}").click().run()
            self.assert_sentinel(app)
            if page == "Makinak":
                app.button(key="machine_details").click().run()
                self.assert_sentinel(app)
                self.assertTrue(any("0.123" in m.value for m in app.markdown))

    def test_null_all_pages_and_modal(self):
        from test_read_contracts import SENTINEL

        row = {
            **SENTINEL,
            **{
                k: None
                for k in ("tenperatura", "rpm", "torque", "higadura", "failure_score")
            },
        }
        app = self.api([row]).run()
        for page in ("Hasiera", "Makinak", "Datuak", "Abisuak"):
            app.query_params["orria"] = page
            app.run()
            self.assert_clean(app)
            self.assertTrue(any(m.value == "Ez dago daturik" for m in app.metric))
            self.assertNotIn("None °C", " ".join(m.value for m in app.markdown))
            if page == "Makinak":
                app.button(key="machine_details").click().run()
                self.assert_clean(app)

    def test_shared_cutoff_visible_age_refresh_and_lazy_history(self):
        from test_read_contracts import SENTINEL

        app = self.api([SENTINEL])
        cutoff = "2026-11-03T00:01:00Z"
        app.session_state["read_as_of"] = cutoff
        app.query_params["orria"] = "Makinak"
        app.run()
        self.assert_clean(app)
        self.assertFalse(any("historikoa" in url for url, _ in self.calls))
        for _, kwargs in self.calls:
            self.assertEqual(kwargs["params"], {"as_of": cutoff})
            self.assertEqual(kwargs["timeout"], (2, 20))
        text = " ".join(m.value for m in app.markdown)
        self.assertIn("Adina (s): 60", text)
        self.assertIn(cutoff, text)
        app.button(key="nav_Datuak").click().run()
        self.assert_clean(app)
        for url, kwargs in self.calls:
            if not url.endswith("model-evaluation"):
                self.assertEqual(kwargs["params"], {"as_of": cutoff})
        app.session_state["history_cursor_CNC-004"] = "old-cutoff"
        next(b for b in app.button if b.label == "Eguneratu").click().run()
        self.assert_clean(app)
        self.assertNotEqual(app.session_state["read_as_of"], cutoff)
        self.assertNotIn("history_cursor_CNC-004", app.session_state)

    def test_live_poll_updates_values_pause_and_empty_recovery(self):
        from test_read_contracts import SENTINEL

        rows = [dict(SENTINEL)]
        app = self.api(rows).run()
        self.assert_clean(app)
        self.assertTrue(app.toggle(key="live_updates").value)
        cutoff = app.session_state["read_as_of"]
        rows[0] = {**SENTINEL, "rpm": 1902}
        app.session_state["live_last_refresh"] = 0
        app.run()
        self.assert_clean(app)
        self.assertNotEqual(app.session_state["read_as_of"], cutoff)
        self.assertTrue(
            any(m.label == "Abiadura (RPM)" and m.value == "1902" for m in app.metric)
        )
        app.toggle(key="live_updates").set_value(False).run()
        cutoff = app.session_state["read_as_of"]
        app.session_state["live_last_refresh"] = 0
        app.run()
        self.assertEqual(app.session_state["read_as_of"], cutoff)
        rows.clear()
        app.toggle(key="live_updates").set_value(True).run()
        self.assert_clean(app)
        self.assertTrue(any("0 makina" in m.value for m in app.info))
        rows.append(dict(SENTINEL))
        self.api_down = True
        app.session_state["live_last_refresh"] = 0
        app.run()
        self.assert_clean(app)
        self.assertTrue(any("DEGRADATUTA" in m.value for m in app.error))
        self.api_down = False
        app.session_state["live_last_refresh"] = 0
        app.run()
        self.assert_sentinel(app)

    def test_due_refresh_preserves_navigation_and_details_clicks(self):
        from test_read_contracts import SENTINEL

        app = self.api([SENTINEL]).run()
        app.session_state["live_last_refresh"] = 0
        app.button(key="nav_Makinak").click().run()
        self.assert_clean(app)
        self.assertEqual(app.session_state["orria"], "Makinak")
        cutoff = app.session_state["read_as_of"]
        app.session_state["live_last_refresh"] = 0
        app.button(key="machine_details").click().run()
        self.assert_clean(app)
        self.assertFalse(app.toggle(key="live_updates").value)
        self.assertEqual(app.session_state["read_as_of"], cutoff)
        self.assertTrue(app.get("dialog"))

    def test_empty_is_valid_duplicate_nan_are_degraded(self):
        from test_read_contracts import SENTINEL

        app = self.api([]).run()
        self.assert_clean(app)
        self.assertFalse(app.error)
        self.assertTrue(any("0 makina" in m.value for m in app.info))
        # Separate test harness mocks for invalid snapshots.
        for rows in ([SENTINEL, SENTINEL], [{**SENTINEL, "rpm": float("nan")}]):
            st.cache_data.clear()
            app = self.api(rows).run()
            self.assert_clean(app)
            self.assertTrue(any("DEGRADATUTA" in m.value for m in app.error))
            self.assertFalse(app.metric)

    def test_period_coverage_binary_evaluation_and_unavailable(self):
        from test_read_contracts import SENTINEL, evaluation_fixture

        app = self.api([SENTINEL], evaluation_payload=evaluation_fixture())
        app.query_params["orria"] = "Datuak"
        app.run()
        self.assert_clean(app)
        self.assertTrue(any("coverage" in j.value for j in app.json))
        self.assertTrue(any(d.value.shape == (2, 2) for d in app.dataframe))
        self.assertTrue(any("FP" in j.value and "FN" in j.value for j in app.json))

    def test_six_month_key_and_partial_history_pagination(self):
        from test_read_contracts import SENTINEL, history_fixture

        payload = history_fixture()
        payload["next_cursor"] = "opaque-token"
        app = self.api([SENTINEL], history_payload=payload)
        app.query_params["orria"] = "Datuak"
        app.session_state["datuak_periodoa"] = "Sei hilabete"
        app.run()
        self.assert_clean(app)
        self.assertTrue(any("coverage" in j.value for j in app.json))
        app.session_state["datuak_periodoa"] = "Laginak"
        app.run()
        self.assert_clean(app)
        self.assertTrue(any("Orrialde partziala" in w.value for w in app.warning))
        cutoff = app.session_state["read_as_of"]
        app.session_state["live_last_refresh"] = 0
        next(b for b in app.button if b.label == "Hurrengo orrialdea").click().run()
        self.assert_clean(app)
        self.assertEqual(app.session_state["history_cursor_CNC-004"], "opaque-token")
        self.assertFalse(app.toggle(key="live_updates").value)
        self.assertEqual(app.session_state["read_as_of"], cutoff)
        app.session_state["live_last_refresh"] = 0
        app.run()
        self.assertEqual(app.session_state["history_cursor_CNC-004"], "opaque-token")

    def test_invalid_evaluation_does_not_render_matrix(self):
        from test_read_contracts import SENTINEL, evaluation_fixture

        payload = evaluation_fixture()
        payload["model_artifact_sha256"] = "wrong"
        app = self.api([SENTINEL], evaluation_payload=payload)
        app.query_params["orria"] = "Datuak"
        app.run()
        self.assert_clean(app)
        self.assertFalse(any(d.value.shape == (2, 2) for d in app.dataframe))
        self.assertTrue(any("bateraezina" in i.value for i in app.info))

    def test_claims_distinguish_current_state_and_cost_scenarios(self):
        from test_read_contracts import SENTINEL

        app = self.api([SENTINEL]).run()
        for page in ("Hasiera", "Makinak", "Datuak", "Abisuak"):
            app.query_params["orria"] = page
            app.run()
            self.assert_clean(app)
            text = " ".join(m.value for m in app.markdown)
            for misleading in (
                "7 eguneko arriskua",
                "Aurreikusitako galera",
                "Akats aktiboa",
                "Arriskurik ez",
            ):
                self.assertNotIn(misleading, text)
            self.assertIn("sentinel", text)
        self.assertEqual(len(app.number_input), 3)
        app.number_input[0].set_value(20).run()
        app.number_input[1].set_value(2).run()
        app.number_input[2].set_value(100).run()
        self.assertTrue(
            any(
                m.label == "Eszenarioaren esposizioa (€)" and m.value == "220"
                for m in app.metric
            )
        )


if __name__ == "__main__":
    unittest.main()
