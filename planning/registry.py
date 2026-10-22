"""Local lab-shadow registry only. No connector to the scoring API or equipment."""

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from planning.online import digest
from scripts.platform_io import exclusive_lock, replace_file, sync_directory


class ShadowRegistry:
    def __init__(self, directory):
        self.root = Path(directory)
        (self.root / "versions").mkdir(parents=True, exist_ok=True)

    @contextmanager
    def locked(self):
        with exclusive_lock(self.root / "registry.lock"):
            yield

    def status(self):
        path = self.root / "pointer.json"
        return (
            json.loads(path.read_text())
            if path.exists()
            else {
                "scope": "LAB_SHADOW_ONLY",
                "active": None,
                "previous": [],
                "audit": [],
            }
        )

    def stage(self, report, state):
        if report.get("runtime_promotion_allowed") is not False:
            raise ValueError("Only lab-shadow artifacts allowed")
        payload = {k: v for k, v in state.items() if k != "checksum"}
        if state.get("version") != 1 or digest(payload) != state.get("checksum"):
            raise ValueError("Valid checksummed model state required")
        artifact = {"scope": "LAB_SHADOW_ONLY", "report": report, "state": state}
        identifier = digest(artifact)
        with self.locked():
            path = self.root / "versions" / f"{identifier}.json"
            if not path.exists():
                self._publish(path, artifact)
            elif digest(json.loads(path.read_text())) != identifier:
                raise ValueError("Corrupt immutable version")
        return identifier

    def _load(self, identifier):
        if (
            not isinstance(identifier, str)
            or len(identifier) != 64
            or any(c not in "0123456789abcdef" for c in identifier)
        ):
            raise ValueError("Invalid version identifier")
        value = json.loads((self.root / "versions" / f"{identifier}.json").read_text())
        if digest(value) != identifier or value.get("scope") != "LAB_SHADOW_ONLY":
            raise ValueError("Corrupt or incompatible version")
        return value

    def _publish(self, path, value):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=path.parent, delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump(value, handle, sort_keys=True, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            replace_file(temporary, path)
            sync_directory(path.parent)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _write(self, pointer):
        self._publish(self.root / "pointer.json", pointer)

    def _transition(self, identifier, expected_active, actor, reason, rollback):
        if (
            not isinstance(actor, str)
            or not actor.strip()
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            raise ValueError("Actor and reason required")
        with self.locked():
            pointer = self.status()
            if pointer["active"] != expected_active:
                raise ValueError("Stale registry update; active version changed")
            if rollback:
                if not pointer["previous"]:
                    raise ValueError("No previous shadow version")
                identifier = pointer["previous"].pop()
            artifact = self._load(identifier)
            if artifact["report"].get("lab_decision") != "ACCEPTED_SHADOW_ONLY":
                raise ValueError("Candidate did not pass shadow acceptance")
            if not rollback:
                report = artifact["report"]
                if report.get("compared_shadow_version") != pointer["active"]:
                    raise ValueError("Evaluation is not bound to the expected champion")
                if pointer["active"]:
                    current = self._load(pointer["active"])
                    if report.get("baseline_kind") != "CURRENT_CHAMPION":
                        raise ValueError("Replacement must beat the current champion")
                    if (
                        artifact["state"].get("manifest_sha256")
                        != current["state"].get("manifest_sha256")
                        or artifact["state"].get("horizon_minutes")
                        != current["state"].get("horizon_minutes")
                        or report.get("champion_alpha") != current["state"].get("alpha")
                    ):
                        raise ValueError(
                            "Incompatible champion manifest/horizon/settings"
                        )
            if pointer["active"] == identifier:
                raise ValueError("Version already active")
            if not rollback and pointer["active"]:
                pointer["previous"].append(pointer["active"])
            pointer["audit"].append(
                {
                    "action": "rollback" if rollback else "activate",
                    "from": pointer["active"],
                    "to": identifier,
                    "actor": actor,
                    "reason": reason,
                    "at": datetime.now(UTC).isoformat(),
                }
            )
            pointer["active"] = identifier
            self._write(pointer)
        return identifier

    def activate(self, identifier, *, expected_active, actor, reason):
        return self._transition(identifier, expected_active, actor, reason, False)

    def rollback(self, *, expected_active, actor, reason):
        return self._transition(None, expected_active, actor, reason, True)
