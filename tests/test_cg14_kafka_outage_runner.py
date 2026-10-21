import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "deploy/cg14/scripts/run-kafka-outage-recovery.py"
SPEC = importlib.util.spec_from_file_location("cg14_outage_runner", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def test_recovery_uses_committed_offset_and_empty_queue_not_resettable_counters():
    offset = {
        "current_offset": 6,
        "log_end_offset": 6,
        "lag": 0,
    }
    assert runner.phase_complete(6, offset, 0)
    # A processor counter may reset and show a negative/low delta; offsets and
    # provenance are the durable observations used to decide completion.
    assert runner.phase_complete(6, offset, 0)
    assert not runner.phase_complete(6, {**offset, "current_offset": 5, "lag": 1}, 0)
    assert not runner.phase_complete(6, offset, 1)
    assert not runner.phase_complete(6, None, 0)


def test_offset_parser_selects_expected_topic_partition():
    output = (
        "GROUP TOPIC PARTITION CURRENT-OFFSET LOG-END-OFFSET LAG CONSUMER-ID HOST CLIENT-ID\n"
        "g other-topic 0 4 4 0 consumer host client\n"
        "g cg14-outage-a 0 6 6 0 consumer host client\n"
    )
    assert runner.e2e.parse_group_offset(output, "cg14-outage-a") == {
        "topic": "cg14-outage-a",
        "partition": 0,
        "current_offset": 6,
        "log_end_offset": 6,
        "lag": 0,
    }
    assert runner.e2e.parse_group_offset(output, "missing") is None


def test_missing_consumer_group_offset_is_retried_as_not_yet_visible(monkeypatch):
    def not_visible(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["docker", "exec"])

    monkeypatch.setattr(runner, "run_docker", not_visible)
    assert runner.offset_row("cg14-outage-a", "cg14-group-a") is None
