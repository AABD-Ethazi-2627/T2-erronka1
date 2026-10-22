"""Resource ownership guards for the explicit recreate lab; no Docker writes."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "deploy/cg14/scripts/run-kafka-volume-recreate.py"
SPEC = importlib.util.spec_from_file_location("volume_runner", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.mark.parametrize(
    "identity,label", [("other-id", "mine"), ("owned-id", "other")]
)
def test_owned_refuses_stale_id_or_wrong_label(identity, label):
    lab = runner.Lab.__new__(runner.Lab)
    lab.ids, lab.run = ["owned-id"], "mine"
    lab.inspect = lambda _: {
        "Id": identity,
        "Config": {"Labels": {runner.LABEL: label}},
    }
    with pytest.raises(RuntimeError, match="ownership"):
        lab.owned("owned-id")


def test_cleanup_never_substitutes_container_name_for_removed_id():
    lab = runner.Lab.__new__(runner.Lab)
    lab.ids, lab.run = ["removed-id", "retained-id"], "mine"
    calls = []

    def docker(*args):
        calls.append(args)
        if args[0] == "ps":
            return "retained-id" if args[-1] == "id=retained-id" else ""
        return ""

    lab.docker = docker
    lab.inspect = lambda _: {
        "Id": "retained-id",
        "Config": {"Labels": {runner.LABEL: "mine"}},
        "State": {"Running": True},
    }
    lab.stop_owned()
    assert ("stop", "--time", "30", "retained-id") in calls
    assert all("removed-id" not in call for call in calls if call[0] != "ps")
    assert not any(call[0] == "rm" for call in calls)


def test_evidence_outside_d_is_rejected():
    with pytest.raises(ValueError, match="/mnt/d/"):
        runner.storage_root("/outside-d/cg14-evidence")


@pytest.mark.parametrize(
    "exit_code,oom,log,accepted",
    [
        (143, False, "[BrokerServer id=1] shut down completed", True),
        (143, False, "begin shutdown", False),
        (137, False, "[BrokerServer id=1] shut down completed", False),
        (143, True, "[BrokerServer id=1] shut down completed", False),
    ],
)
def test_shutdown_requires_completed_hook_without_kill_or_oom(
    exit_code, oom, log, accepted
):
    lab = runner.Lab.__new__(runner.Lab)
    lab.owned = lambda _: {"State": {"ExitCode": exit_code, "OOMKilled": oom}}
    lab.save = lambda *args: None
    lab.docker = lambda *args: log if args[0] == "logs" else ""
    if accepted:
        lab.stop_cleanly("owned-id", "state.json")
    else:
        with pytest.raises(RuntimeError, match="shutdown"):
            lab.stop_cleanly("owned-id", "state.json")
