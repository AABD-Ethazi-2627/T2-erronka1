"""Streamlit regression checks; no API server or industrial connection required."""

import os
import unittest
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
