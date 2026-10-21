"""Safety regression for the offline/host-only restore client; no live NiFi."""

import json
import ssl
import urllib.error
from email.parser import BytesParser
from email.policy import default
from io import BytesIO
from pathlib import Path

import pytest

import cg14_restore_upload as restore

FLOW = (
    Path(restore.__file__).parent
    / "nifi-flows/cg14_validation_flow_nifi_2.12.0_restore_safe_20261020.json"
)


def test_preflight_approved_artifact_and_tamper_rejection(tmp_path):
    raw, result = restore.preflight(FLOW)
    assert result["all_disabled"] and result["processors"] == 23
    modified = tmp_path / "modified.json"
    data = json.loads(raw)
    data["flowContents"]["processors"][0]["scheduledState"] = "RUNNING"
    modified.write_text(json.dumps(data))
    with pytest.raises(restore.GuardError, match="SHA256"):
        restore.preflight(modified)


def test_preflight_does_not_create_api_or_use_network(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline preflight attempted network/API construction")

    monkeypatch.setattr(restore, "Api", forbidden)
    monkeypatch.setattr(
        restore.ssl, "create_default_context", lambda **kwargs: object()
    )
    assert restore.main(["--flow", str(FLOW)]) == 0
    assert "Sin red ni importación" in capsys.readouterr().out


def test_multipart_preserves_exact_file_and_target():
    raw = FLOW.read_bytes()
    body, content_type = restore.multipart(raw)
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
    )
    parts = {
        part.get_param("name", header="content-disposition"): part
        for part in message.iter_parts()
    }
    assert parts["file"].get_payload(decode=True) == raw
    assert parts["groupName"].get_content().strip() == restore.TARGET
    assert parts["disconnectedNodeAcknowledged"].get_content().strip() == "false"


def test_redirect_never_forwards_authentication():
    with pytest.raises(restore.GuardError, match="Redirección"):
        restore.NoRedirect().redirect_request(
            None, None, 302, "", {}, "https://example.com"
        )


def test_existing_target_prevents_upload():
    class FakeApi:
        def flow(self, group):
            return {
                "flow": {"processGroups": [{"component": {"name": restore.TARGET}}]}
            }

    with pytest.raises(restore.GuardError, match="ya existe"):
        restore.ensure_absent(FakeApi(), "root")


def test_uncertain_upload_is_not_retried_and_keeps_evidence(tmp_path, monkeypatch):
    requests = []

    class FakeApi:
        token = None

        def __init__(self, context):
            pass

        def login(self):
            pass

        def flow(self, group):
            return {"id": "root-id", "flow": {"processGroups": []}}

        def request(self, *args):
            requests.append(args)
            raise urllib.error.URLError("simulated lost response")

    monkeypatch.setattr(restore, "REPO", tmp_path)
    monkeypatch.setattr(restore, "Api", FakeApi)
    monkeypatch.setattr(restore, "original_fingerprint", lambda api: "same-original")
    monkeypatch.setattr(
        restore.ssl, "create_default_context", lambda **kwargs: object()
    )
    monkeypatch.setattr("builtins.input", lambda prompt: "IMPORTAR")
    with pytest.raises(urllib.error.URLError):
        restore.main(["--flow", str(FLOW), "--execute"])
    assert len(requests) == 1
    assert requests[0][0] == "/process-groups/root-id/process-groups/upload"
    evidence = list(
        tmp_path.glob("deploy/cg14/data/evidence/restore-upload-*/result.json")
    )
    assert len(evidence) == 1
    result = json.loads(evidence[0].read_text())
    assert result["upload"] == "SENDING_OUTCOME_NOT_YET_KNOWN"
    assert result["original_unchanged"] is True
    assert "Inspeccionar" in result["follow_up"]


@pytest.mark.parametrize("upload_status", [200, 201])
def test_follow_up_http_error_preserves_successful_upload(
    tmp_path, monkeypatch, upload_status
):
    requests = []

    class FakeApi:
        token = None

        def __init__(self, context):
            pass

        def login(self):
            pass

        def flow(self, group):
            return {"id": "root-id", "flow": {"processGroups": []}}

        def request(self, *args):
            requests.append(args)
            return upload_status, json.dumps(
                {"component": {"id": "new-group", "name": restore.TARGET}}
            ).encode()

    def unavailable(*args):
        raise urllib.error.HTTPError(
            "https://localhost/flow", 503, "unavailable", {}, None
        )

    monkeypatch.setattr(restore, "REPO", tmp_path)
    monkeypatch.setattr(restore, "Api", FakeApi)
    monkeypatch.setattr(restore, "original_fingerprint", lambda api: "same-original")
    monkeypatch.setattr(restore, "observe", unavailable)
    monkeypatch.setattr(
        restore.ssl, "create_default_context", lambda **kwargs: object()
    )
    monkeypatch.setattr("builtins.input", lambda prompt: "IMPORTAR")
    with pytest.raises(urllib.error.HTTPError):
        restore.main(["--flow", str(FLOW), "--execute"])
    assert len(requests) == 1
    evidence = next(
        tmp_path.glob("deploy/cg14/data/evidence/restore-upload-*/result.json")
    )
    result = json.loads(evidence.read_text())
    assert result["http_status"] == upload_status
    assert result["upload"] == "RESPONDED"
    assert result["imported_group_id"] == "new-group"
    assert result["post_import_http_error"] == 503
    assert result["upload_http_status"] == upload_status
    assert result["upload_succeeded"] is True
    assert result["postcheck_succeeded"] is False
    assert result["postcheck_error"] == {"kind": "HTTPError", "http_status": 503}


@pytest.mark.parametrize("include_id", [True, False])
def test_successful_201_checks_created_group_once(tmp_path, monkeypatch, include_id):
    writes = []
    reads = []
    observed_ids = []

    class FakeApi:
        token = None

        def __init__(self, context):
            pass

        def login(self):
            pass

        def flow(self, group):
            reads.append(group)
            groups = (
                [{"component": {"name": restore.TARGET, "id": "created-id"}}]
                if writes
                else []
            )
            return {"id": "parent-id", "flow": {"processGroups": groups}}

        def request(self, *args):
            writes.append(args)
            component = {"name": restore.TARGET}
            if include_id:
                component["id"] = "created-id"
            return 201, json.dumps({"component": component}).encode()

    def observed(api, group_id, definition):
        observed_ids.append(group_id)
        return {"definition_checks_passed": True}

    monkeypatch.setattr(restore, "REPO", tmp_path)
    monkeypatch.setattr(restore, "Api", FakeApi)
    monkeypatch.setattr(restore, "observe", observed)
    monkeypatch.setattr(restore, "original_fingerprint", lambda api: "unchanged")
    monkeypatch.setattr(
        restore.ssl, "create_default_context", lambda **kwargs: object()
    )
    monkeypatch.setattr("builtins.input", lambda prompt: "IMPORTAR")
    assert restore.main(["--flow", str(FLOW), "--execute"]) == 0
    assert len(writes) == 1
    assert observed_ids == ["created-id"]
    assert reads.count("parent-id") == (2 if include_id else 3)
    result = json.loads(
        next(
            tmp_path.glob("deploy/cg14/data/evidence/restore-upload-*/result.json")
        ).read_text()
    )
    assert result["upload_http_status"] == 201
    assert result["upload_succeeded"] is True
    assert result["postcheck_succeeded"] is True
    assert result["postcheck_error"] is None
    assert result["imported_group_id"] == "created-id"
    assert result["imported_group_id_source"] == (
        "upload_response" if include_id else "parent_children_get"
    )


@pytest.mark.parametrize("matches", [0, 2])
def test_missing_id_fallback_rejects_absence_and_duplicates(matches):
    class ReadOnlyApi:
        def flow(self, group):
            assert group == "parent"
            return {
                "flow": {
                    "processGroups": [
                        {"component": {"name": restore.TARGET, "id": str(i)}}
                        for i in range(matches)
                    ]
                }
            }

    with pytest.raises(restore.GuardError, match="único"):
        restore.resolve_created_group(ReadOnlyApi(), "parent", b'{"component":{}}')


def test_created_group_cannot_be_original():
    with pytest.raises(restore.GuardError, match="original"):
        restore.resolve_created_group(
            None,
            "parent",
            json.dumps(
                {"component": {"name": restore.TARGET, "id": restore.ORIGINAL}}
            ).encode(),
        )


class StubResponse:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class StubOpener:
    def __init__(self, handler):
        self.handler = handler
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        return self.handler(request)


def api_with_stub(handler):
    api = restore.Api(ssl.create_default_context())
    api.opener = StubOpener(handler)
    return api


def test_login_negotiates_plain_text_and_accepts_201(monkeypatch, capsys):
    def nifi_token_contract(request):
        assert request.get_method() == "POST"
        assert request.full_url.endswith("/nifi-api/access/token")
        assert request.get_header("Accept") == "text/plain"
        assert request.get_header("Content-type") == "application/x-www-form-urlencoded"
        return StubResponse(201, b"synthetic-test-token")

    api = api_with_stub(nifi_token_contract)
    monkeypatch.setattr("builtins.input", lambda prompt: "synthetic-user")
    monkeypatch.setattr(restore.getpass, "getpass", lambda prompt: "synthetic-password")
    api.login()
    assert api.token == "synthetic-test-token"
    assert len(api.opener.requests) == 1
    output = capsys.readouterr()
    for secret in ("synthetic-user", "synthetic-password", "synthetic-test-token"):
        assert secret not in output.out + output.err


def test_get_root_negotiates_json(capsys):
    api = api_with_stub(
        lambda request: StubResponse(200, b'{"processGroupFlow":{"id":"root"}}')
    )
    api.token = "synthetic-bearer"
    assert api.flow("root")["id"] == "root"
    request = api.opener.requests[0]
    assert request.get_method() == "GET"
    assert request.get_header("Accept") == "application/json"
    assert request.get_header("Content-type") is None
    assert request.get_header("Authorization") == "Bearer synthetic-bearer"
    output = capsys.readouterr()
    assert "synthetic-bearer" not in output.out + output.err


def test_upload_request_negotiates_json_and_valid_multipart_boundary():
    api = api_with_stub(lambda request: StubResponse(200, b"{}"))
    raw = FLOW.read_bytes()
    body, content_type = restore.multipart(raw)
    api.request("/process-groups/root/process-groups/upload", body, content_type)
    request = api.opener.requests[0]
    assert request.get_method() == "POST"
    assert request.get_header("Accept") == "application/json"
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {request.get_header('Content-type')}\r\n\r\n".encode()
        + request.data
    )
    assert message.get_content_type() == "multipart/form-data"
    assert message.get_boundary().startswith("cg14-")
    parts = {
        p.get_param("name", header="content-disposition"): p
        for p in message.iter_parts()
    }
    assert parts["file"].get_payload(decode=True) == raw
    assert len(api.opener.requests) == 1


@pytest.mark.parametrize(
    "path,expected_method,content_type",
    [
        ("/access/token", "POST", "application/x-www-form-urlencoded"),
        ("/flow/process-groups/root", "GET", None),
        (
            "/process-groups/root/process-groups/upload",
            "POST",
            "multipart/form-data; boundary=cg14-test",
        ),
    ],
)
def test_406_diagnostic_identifies_phase_without_secrets(
    path, expected_method, content_type, capsys
):
    secret = "synthetic-sensitive-marker"

    def reject(request):
        # Error reason, headers and response body are all deliberately sensitive.
        raise urllib.error.HTTPError(
            request.full_url,
            406,
            secret,
            {"Set-Cookie": secret},
            BytesIO(secret.encode()),
        )

    api = api_with_stub(reject)
    api.token = secret
    with pytest.raises(urllib.error.HTTPError) as raised:
        api.request(path, secret.encode() if content_type else None, content_type)
    assert raised.value.code == 406
    assert len(api.opener.requests) == 1
    output = capsys.readouterr()
    diagnostic = output.out + output.err
    assert "HTTP 406" in diagnostic
    assert "METHOD: " + expected_method in diagnostic
    assert "PATH: /nifi-api" + path in diagnostic
    assert "ACCEPT: application/json" in diagnostic
    assert "CONTENT-TYPE: " + (content_type or "(none)") in diagnostic
    for excluded in (secret, "Authorization", "Bearer", "Set-Cookie"):
        assert excluded not in diagnostic


def test_login_406_aborts_before_confirmation_or_upload(monkeypatch, capsys):
    def reject(request):
        raise urllib.error.HTTPError(
            request.full_url, 406, "sensitive-reason", {}, None
        )

    api = api_with_stub(reject)
    prompts = []

    def username_only(prompt):
        prompts.append(prompt)
        assert "IMPORTAR" not in prompt
        return "synthetic-user"

    monkeypatch.setattr(restore, "Api", lambda context: api)
    # The HTTP 406 test owns TLS setup; no local CA or credentials are required.
    monkeypatch.setattr(
        restore.ssl,
        "create_default_context",
        lambda **kw: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
    )
    monkeypatch.setattr("builtins.input", username_only)
    monkeypatch.setattr(restore.getpass, "getpass", lambda prompt: "synthetic-password")
    with pytest.raises(urllib.error.HTTPError):
        restore.main(["--flow", str(FLOW), "--execute"])
    assert len(prompts) == 1
    assert len(api.opener.requests) == 1
    assert api.opener.requests[0].full_url.endswith("/access/token")
    output = capsys.readouterr()
    assert "PATH: /nifi-api/access/token" in output.err
    assert "ACCEPT: text/plain" in output.err
    assert "synthetic-password" not in output.out + output.err
