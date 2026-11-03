"""AppTest over actual loopback API/ES/CG15; not browser timer acceptance."""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def run(api_url, evidence, output, unavailable=None):
    from streamlit.testing.v1 import AppTest, app_test

    address = urlsplit(api_url)
    if (
        address.scheme != "http"
        or address.hostname not in {"127.0.0.1", "localhost", "::1"}
        or not address.port
    ):
        raise ValueError("Explicit loopback API required")
    evidence, output = Path(evidence), Path(output)
    initial = json.loads((evidence / "0-snapshot.json").read_text())[0]
    latest = json.loads((evidence / "1-snapshot.json").read_text())[0]
    os.environ.update(LANEKI_MODE="api", LANEKI_API_URL=api_url.rstrip("/") + "/api")
    app = AppTest.from_file(str(ROOT / "dashboard_laneki/app.py"), default_timeout=60)
    # [start,end) excludes sample2 at its exact timestamp: real ES selects sample1.
    app.session_state["read_as_of"] = latest["timestamp"]
    observations = []

    def verify(label, expected):
        if app.exception:
            raise AssertionError(str(app.exception))
        values = {metric.label: metric.value for metric in app.metric}
        for key, title in (
            ("rpm", "Abiadura (RPM)"),
            ("tenperatura", "Prozesu-tenperatura (°C)"),
            ("torque", "Bihurdura-momentua (Nm)"),
            ("higadura", "Erremintaren higadura (min)"),
        ):
            assert values[title] == f"{expected[key]:g}", (label, title, values)
        text = "\n".join(m.value for m in app.markdown)
        assert expected["event_key"] in text, label
        assert not app.error, label
        observations.append(
            {
                "page": label,
                "event_key": expected["event_key"],
                "values": values,
                "cutoff": app.session_state["read_as_of"],
            }
        )

    try:
        app.run()
        if unavailable:
            assert not app.exception
            assert any("DEGRADATUTA" in e.value for e in app.error)
            assert not app.metric
            assert app.toggle(key="live_updates").value
            report = {
                "status": "passed",
                "transport": "real_loopback_HTTP",
                "ui": "Streamlit_AppTest",
                "browser": False,
                "unavailable_component": unavailable,
                "degraded_without_demo": True,
            }
            with output.open("x") as handle:
                json.dump(report, handle, indent=2)
            return report
        verify("Hasiera_initial_cutoff", initial)
        app.session_state["live_last_refresh"] = 0
        app.run()
        verify("Hasiera_after_refresh", latest)
        for page in ("Makinak", "Datuak", "Abisuak"):
            app.button(key=f"nav_{page}").click().run()
            verify(page, latest)
            if page == "Makinak":
                app.button(key="machine_details").click().run()
                verify("Makinak_modal", latest)
        report = {
            "status": "passed",
            "transport": "real_loopback_HTTP",
            "ui": "Streamlit_AppTest",
            "browser": False,
            "timer": "elapsed_state_triggered_not_wall_clock_browser",
            "source": str(evidence),
            "observations": observations,
        }
        with output.open("x") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
        return report
    finally:
        app_test.TMP_DIR.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect-unavailable", choices=["ES", "API"])
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.api_url, args.run_dir, args.output, args.expect_unavailable),
            indent=2,
            ensure_ascii=False,
        )
    )
