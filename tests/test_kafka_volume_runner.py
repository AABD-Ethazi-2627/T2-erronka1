"""Resource ownership guards for the explicit recreate lab; no Docker writes."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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
    "baseline,current",
    [
        (
            "A /lab\nA /lab/runtime\nA /lab/server.properties\nA /lab/start.sh",
            "A /lab\nA /lab/server.properties\nA /lab/start.sh\nA /lab/runtime",
        ),
        ("C /a b\nD /ñ/\u2028x\nA /tail \n", "A /tail \nC /a b\nD /ñ/\u2028x\n"),
        ("A /same\nA /same\nC /other", "C /other\nA /same\nA /same"),
    ],
)
def test_layer_accepts_reordered_entries(baseline, current):
    lab = runner.Lab.__new__(runner.Lab)
    lab.layer_baselines = {"owned-id": baseline}
    lab.docker = lambda *args: current
    lab.check_layer("owned-id")


@pytest.mark.parametrize(
    "current",
    [
        "A /lab\nA /lab/runtime\nA /unexpected",
        "A /lab\nA /lab/runtime\nC /unexpected",
        "A /lab\nA /lab/runtime\nD /unexpected",
        "A /lab",  # missing entry
        "A /lab\nC /lab/runtime",  # changed type
        "A /lab\nA /lab/runtime\nA /lab/runtime",  # extra duplicate
        "A /lab\nA /lab/runtime-extra",  # prefix is not a path match
        "A /lab\nA /lab/runtime ",  # trailing space belongs to the path
        "A /lab\nA /lab/ru\u2028ntime",  # Unicode line separator is path data
    ],
)
def test_layer_rejects_changed_entries(current):
    lab = runner.Lab.__new__(runner.Lab)
    lab.layer_baselines = {"owned-id": "A /lab\nA /lab/runtime"}
    lab.docker = lambda *args: current
    with pytest.raises(RuntimeError, match="container layer"):
        lab.check_layer("owned-id")


def test_layer_rejects_missing_duplicate():
    lab = runner.Lab.__new__(runner.Lab)
    lab.layer_baselines = {"owned-id": "A /same\nA /same"}
    lab.docker = lambda *args: "A /same"
    with pytest.raises(RuntimeError, match="container layer"):
        lab.check_layer("owned-id")


@pytest.mark.parametrize(
    "output",
    ["\n", "A /ok\n\n", "X /bad", "A relative", "A", "A  /bad", " /bad"],
)
def test_layer_rejects_malformed_even_when_identical(output):
    lab = runner.Lab.__new__(runner.Lab)
    lab.layer_baselines = {"owned-id": output}
    lab.docker = lambda *args: output
    with pytest.raises(RuntimeError, match="Malformed docker diff"):
        lab.check_layer("owned-id")


@pytest.mark.parametrize("output", ["", "A /\n", "C /space \nD /é\n"])
def test_layer_accepts_empty_or_identical_entries(output):
    lab = runner.Lab.__new__(runner.Lab)
    lab.layer_baselines = {"owned-id": output}
    lab.docker = lambda *args: output
    lab.check_layer("owned-id")


def test_layer_preserves_unicode_path_spelling():
    lab = runner.Lab.__new__(runner.Lab)
    lab.layer_baselines = {"owned-id": "A /é"}
    lab.docker = lambda *args: "A /e\u0301"
    with pytest.raises(RuntimeError, match="container layer"):
        lab.check_layer("owned-id")


def test_docker_diff_does_not_strip_path_whitespace(monkeypatch, tmp_path):
    output = "A / space \nC /ñ/\u2028x\n"
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, output, ""),
    )
    lab = runner.Lab.__new__(runner.Lab)
    lab.root = tmp_path
    assert lab.docker("diff", "owned-id") == output


@pytest.mark.parametrize("kind", ["kafka", "io", "bug"])
def test_readiness_retries_broker_errors_but_propagates_bugs(
    monkeypatch, tmp_path, kind
):
    calls = []

    class KafkaError(Exception):
        pass

    error = {
        "kafka": KafkaError("not ready"),
        "io": ConnectionError("not ready"),
        "bug": RuntimeError("bug"),
    }[kind]

    def admin(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise error
        return SimpleNamespace(close=lambda: None)

    monkeypatch.setitem(sys.modules, "kafka", SimpleNamespace(KafkaAdminClient=admin))
    monkeypatch.setitem(
        sys.modules, "kafka.errors", SimpleNamespace(KafkaError=KafkaError)
    )
    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    lab = runner.Lab.__new__(runner.Lab)
    lab.root = tmp_path
    lab.owned = lambda _: {"State": {"Running": True}}
    if kind != "bug":
        lab.ready("owned-id", "127.0.0.1:9092")
        assert len(calls) == 2
        assert (tmp_path / "readiness-last-error.txt").read_text() == repr(error)
    else:
        with pytest.raises(RuntimeError, match="bug"):
            lab.ready("owned-id", "127.0.0.1:9092")
        assert len(calls) == 1


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
