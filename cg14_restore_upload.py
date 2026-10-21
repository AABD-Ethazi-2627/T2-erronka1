#!/usr/bin/env python3
"""Upload the approved CG14 copy from the host. Default: offline preflight only.

Uses only the Python standard library. Never starts, enables, replaces or deletes
NiFi components. An upload with an uncertain outcome must be investigated, not
retried blindly. This validates a definition import, not disaster recovery.
"""

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


REPO = Path(__file__).resolve().parent
FLOW_SHA256 = "98bcdaa8e64d197644b2e7a1c409394f50b4c8df2946780d442c109d2658839b"
TARGET = "CNC-GUARD-CG14-RESTORE-TEST"
ORIGINAL = "583bcfb5-01a1-1000-de1a-41cdf8ea78fe"
API_BASE = "https://localhost:18443/nifi-api"


class GuardError(ValueError):
    """A fixed, non-sensitive safety diagnostic suitable for the console."""


def require(condition, message):
    if not condition:
        raise GuardError(message)


def preflight(path):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == FLOW_SHA256, "SHA256 distinto de la copia autorizada; no importar.")
    definition = json.loads(raw)
    flow = definition["flowContents"]
    processors = flow["processors"]
    connections = flow["connections"]
    services = flow["controllerServices"]
    require((len(processors), len(connections), len(services)) == (23, 27, 1),
            "Conteos inesperados.")
    for key in ("externalControllerServices", "parameterContexts", "parameterProviders"):
        require(not definition.get(key), "Dependencias externas no permitidas.")
    for key in ("processGroups", "remoteProcessGroups", "inputPorts", "outputPorts", "funnels"):
        require(not flow.get(key), "Componentes externos o anidados no permitidos.")
    components = processors + services
    ids = {p["identifier"] for p in components}
    service_ids = {s["identifier"] for s in services}
    require(len(ids) == 24, "Identificadores duplicados.")
    for component in components:
        require(component.get("scheduledState") == "DISABLED", "Componente habilitado.")
        require(component.get("bundle", {}).get("version") == "2.12.0", "Bundle incompatible.")
        for name, descriptor in component.get("propertyDescriptors", {}).items():
            value = component.get("properties", {}).get(name)
            require(not (descriptor.get("sensitive") and value), "Propiedad sensible configurada.")
            if descriptor.get("identifiesControllerService") and value:
                require(value in service_ids, "Referencia externa a Controller Service.")
    for connection in connections:
        for end in ("source", "destination"):
            require(connection[end]["id"] in ids, "Referencia de conexión sin resolver.")
    return raw, {"sha256": digest, "processors": 23, "connections": 27,
                 "controller_services": 1, "all_disabled": True,
                 "bundles": "2.12.0", "network_used": False}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise GuardError("Redirección rechazada; no reenviar credenciales.")


class Api:
    def __init__(self, context):
        # Do not use proxy environment variables for local credentials or TLS.
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect(),
            urllib.request.HTTPSHandler(context=context))
        self.token = None

    @staticmethod
    def diagnose(request, status):
        # Allowlist request metadata only: never response bodies/headers, forms,
        # Authorization, cookies or exception reasons (which may contain secrets).
        print(
            f"HTTP {status}\n"
            f"METHOD: {request.get_method()}\n"
            f"PATH: {urllib.parse.urlsplit(request.full_url).path}\n"
            f"ACCEPT: {request.get_header('Accept')}\n"
            f"CONTENT-TYPE: {request.get_header('Content-type') or '(none)'}",
            file=sys.stderr,
        )

    def request(self, path, data=None, content_type=None, *, accept="application/json"):
        headers = {"Accept": accept}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(API_BASE + path, data=data, headers=headers)
        try:
            with self.opener.open(request, timeout=60) as response:
                self.diagnose(request, response.status)
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            self.diagnose(request, error.code)
            raise

    def login(self):
        username = input("Usuario NiFi (no se guardará): ").strip()
        require(bool(username), "Usuario NiFi vacío tras normalizar; autenticación no enviada.")
        password = getpass.getpass("Contraseña NiFi (entrada oculta): ")
        try:
            status, raw = self.request("/access/token", urllib.parse.urlencode(
                {"username": username, "password": password}).encode(),
                "application/x-www-form-urlencoded", accept="text/plain")
            require(status in (200, 201), "Autenticación no confirmada.")
            self.token = raw.decode().strip()
            require(bool(self.token), "Token vacío.")
        finally:
            password = None

    def get(self, path):
        return json.loads(self.request(path)[1])

    def flow(self, group_id):
        return self.get(f"/flow/process-groups/{group_id}")["processGroupFlow"]


def components(api, group_id):
    flow = api.flow(group_id)["flow"]
    services = api.get(f"/flow/process-groups/{group_id}/controller-services")
    return flow, [x["component"] for x in services["controllerServices"]]


def original_fingerprint(api):
    flow, services = components(api, ORIGINAL)
    # Hash configuration and states in memory; never write properties to evidence.
    snapshot = {"processors": [], "connections": [], "services": []}
    for entity in flow.get("processors", []):
        component = entity["component"]
        snapshot["processors"].append({k: component.get(k) for k in
            ("id", "name", "type", "bundle", "state", "config")})
    for entity in flow.get("connections", []):
        snapshot["connections"].append(entity["component"])
    for service in services:
        snapshot["services"].append({k: service.get(k) for k in
            ("id", "name", "type", "bundle", "state", "properties")})
    for value in snapshot.values():
        value.sort(key=lambda item: item["id"])
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def ensure_absent(api, root_id):
    names = [g["component"]["name"] for g in api.flow(root_id)["flow"].get("processGroups", [])]
    require(TARGET not in names, "El grupo destino ya existe: inspeccionarlo; no duplicar.")


def resolve_created_group(api, root_id, response):
    """Resolve an already successful upload; only GET fallback, never upload again."""
    try:
        payload = json.loads(response)
    except (ValueError, UnicodeDecodeError):
        payload = {}
    component = payload.get("component") if isinstance(payload, dict) else None
    component = component if isinstance(component, dict) else {}
    if component.get("name"):
        require(component["name"] == TARGET, "Respuesta con nombre de grupo inesperado.")
    group_id = component.get("id")
    source = "upload_response"
    if not group_id:
        matches = [g["component"] for g in api.flow(root_id)["flow"].get("processGroups", [])
                   if g["component"].get("name") == TARGET]
        require(len(matches) == 1, "No hay un único grupo destino; detener sin repetir upload.")
        group_id = matches[0].get("id")
        source = "parent_children_get"
    require(isinstance(group_id, str) and bool(group_id), "Grupo destino sin ID válido.")
    require(group_id != ORIGINAL, "Respuesta inesperada: ID del grupo original. Detener y revisar.")
    return group_id, source


def multipart(raw):
    boundary = "cg14-" + uuid.uuid4().hex
    body = bytearray()
    fields = {"groupName": TARGET, "positionX": "1200", "positionY": "400",
              "clientId": str(uuid.uuid4()), "disconnectedNodeAcknowledged": "false"}
    for key, value in fields.items():
        body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"'
                     f'\r\n\r\n{value}\r\n').encode())
    body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                 'filename="cg14-restore-safe.json"\r\nContent-Type: application/json\r\n\r\n').encode())
    body.extend(raw)
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    return bytes(body), "multipart/form-data; boundary=" + boundary


def observe(api, group_id, definition):
    flow, services = components(api, group_id)
    processors = [p["component"] for p in flow.get("processors", [])]
    connections = [c["component"] for c in flow.get("connections", [])]
    ids = {p["id"] for p in processors}
    service_ids = {s["id"] for s in services}
    unresolved = sum(c[end]["id"] not in ids for c in connections for end in ("source", "destination"))
    external_service_refs = 0
    for processor in processors + services:
        config = processor.get("config", processor)
        for key, descriptor in config.get("descriptors", {}).items():
            value = config.get("properties", {}).get(key)
            if descriptor.get("identifiesControllerService") and value and value not in service_ids:
                external_service_refs += 1
    expected = definition["flowContents"]
    def signature(component):
        return (component.get("name"), component.get("type"),
                json.dumps(component.get("bundle"), sort_keys=True))
    names = {p["id"]: p["name"] for p in processors}
    expected_names = {p["identifier"]: p["name"] for p in expected["processors"]}
    def edges(items, lookup):
        return sorted((lookup.get(c["source"]["id"], "UNRESOLVED"),
                       lookup.get(c["destination"]["id"], "UNRESOLVED"),
                       tuple(sorted(c.get("selectedRelationships", [])))) for c in items)
    component_types_match = (
        sorted(map(signature, processors)) == sorted(map(signature, expected["processors"]))
        and sorted(map(signature, services)) == sorted(map(signature, expected["controllerServices"]))
    )
    relationships_match = edges(connections, names) == edges(expected["connections"], expected_names)
    result = {
        "group_id": group_id, "processors": len(processors),
        "connections": len(connections), "controller_services": len(services),
        "processor_states": [{"id": p["id"], "state": p.get("state"),
                              "validation_status": p.get("validationStatus"),
                              "validation_error_count": len(p.get("validationErrors", [])),
                              "type": p.get("type"), "bundle": p.get("bundle")}
                             for p in processors],
        "services": [{"id": s["id"], "state": s.get("state"),
                      "validation_status": s.get("validationStatus"),
                      "validation_error_count": len(s.get("validationErrors", [])),
                      "type": s.get("type"), "bundle": s.get("bundle")}
                     for s in services],
        "unresolved_connection_endpoints": unresolved,
        "external_service_refs": external_service_refs,
        "component_types_bundles_match_export": component_types_match,
        "connection_relationships_match_export": relationships_match,
        "functional_fixtures": "NOT_TESTED", "service_enablement": "NOT_TESTED",
        "disaster_recovery": "NOT_TESTED",
    }
    result["definition_checks_passed"] = (
        (len(processors), len(connections), len(services)) == (23, 27, 1)
        and not unresolved and not external_service_refs
        and component_types_match and relationships_match
        and not any(flow.get(k) for k in ("processGroups", "remoteProcessGroups", "inputPorts", "outputPorts"))
        and all(p.get("state") == "DISABLED" for p in processors + services)
        and all(p.get("bundle", {}).get("version") == "2.12.0" for p in processors + services)
    )
    return result


def save(path, evidence):
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flow", type=Path, default=REPO / "nifi-flows/cg14_validation_flow_nifi_2.12.0_restore_safe_20261020.json")
    parser.add_argument("--cert", type=Path, default=REPO / "deploy/cg14/secrets/nifi-local.crt")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    raw, preflight_result = preflight(args.flow)
    context = ssl.create_default_context(cafile=str(args.cert))
    print("PREFLIGHT:", json.dumps(preflight_result))
    if not args.execute:
        print("Sin red ni importación. Ejecutar en el host con --execute para continuar.")
        return 0
    api = Api(context)
    api.login()
    root_id = api.flow("root")["id"]
    ensure_absent(api, root_id)
    baseline = original_fingerprint(api)
    print("Destino:", API_BASE, "grupo nuevo:", TARGET)
    require(input("Escribe IMPORTAR para enviar un único POST: ") == "IMPORTAR", "Cancelado.")
    ensure_absent(api, root_id)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = REPO / "deploy/cg14/data/evidence" / ("restore-upload-" + run_id)
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    path = directory / "result.json"
    evidence = {"timestamp_utc": run_id, "preflight": preflight_result,
                "target_name": TARGET, "original_id": ORIGINAL,
                "original_before_sha256": baseline, "upload": "NOT_SENT",
                "upload_http_status": None, "upload_succeeded": None,
                "postcheck_succeeded": False, "postcheck_error": None}
    save(path, evidence)
    try:
        data, content_type = multipart(raw)
        evidence["upload"] = "SENDING_OUTCOME_NOT_YET_KNOWN"
        save(path, evidence)
        # Exactly one attempt. Do not retry after HTTP/network errors.
        status, response = api.request(f"/process-groups/{root_id}/process-groups/upload", data, content_type)
        evidence["http_status"] = status
        evidence["upload_http_status"] = status
        evidence["upload_succeeded"] = status in (200, 201)
        evidence["upload"] = "RESPONDED"
        save(path, evidence)
        require(evidence["upload_succeeded"], "Respuesta HTTP inesperada; inspeccionar destino antes de reintentar.")
        group_id, id_source = resolve_created_group(api, root_id, response)
        evidence.update(imported_group_id=group_id, imported_group_id_source=id_source)
        save(path, evidence)
        print("IMPORTACIÓN RESPONDIDA: HTTP", status, "Process Group ID:", group_id)
        evidence["observed"] = observe(api, group_id, json.loads(raw))
        evidence["postcheck_succeeded"] = evidence["observed"]["definition_checks_passed"]
        if not evidence["postcheck_succeeded"]:
            evidence["postcheck_error"] = {"kind": "DefinitionChecksFailed"}
        print(json.dumps(evidence["observed"], indent=2))
    except urllib.error.HTTPError as error:
        if evidence["upload_succeeded"] is True:
            # A failed read after creation does not change the upload response.
            evidence["post_import_http_error"] = error.code
            evidence["postcheck_error"] = {"kind": "HTTPError", "http_status": error.code}
        else:
            evidence.update(upload="HTTP_ERROR_DO_NOT_RETRY_BLINDLY", http_status=error.code)
            evidence.update(upload_http_status=error.code, upload_succeeded=False)
        evidence["follow_up"] = "Inspeccionar grupo destino antes de cualquier nuevo upload."
        raise
    except Exception as error:
        if evidence["upload_succeeded"] is True:
            evidence["postcheck_error"] = {"kind": type(error).__name__}
        evidence["follow_up"] = "Inspeccionar grupo destino antes de cualquier nuevo upload."
        raise
    finally:
        try:
            evidence["original_after_sha256"] = original_fingerprint(api)
            evidence["original_unchanged"] = evidence["original_after_sha256"] == baseline
        except Exception:
            evidence["original_unchanged"] = "NOT_TESTED"
        if evidence["original_unchanged"] is not True:
            evidence["postcheck_succeeded"] = False
            if evidence["postcheck_error"] is None:
                evidence["postcheck_error"] = {"kind": "OriginalIntegrityNotConfirmed"}
        save(path, evidence)
        print("Evidencia sin credenciales:", path)
        api.token = None
    return 0 if evidence["postcheck_succeeded"] else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.HTTPError as error:
        print(f"ERROR HTTP {error.code}; cuerpo omitido. No reintentar automáticamente.", file=sys.stderr)
        sys.exit(2)
    except (urllib.error.URLError, ssl.SSLError):
        print("ERROR de conexión/TLS. No se omite TLS ni se reintenta el upload.", file=sys.stderr)
        sys.exit(2)
    except GuardError as error:
        print("Operación detenida:", str(error), file=sys.stderr)
        sys.exit(2)
    except (ValueError, KeyError, OSError, EOFError, KeyboardInterrupt) as error:
        # Exception bodies can contain server data; print only the exception type.
        print(f"Operación detenida ({type(error).__name__}); no repetir upload sin revisar evidencia.", file=sys.stderr)
        sys.exit(2)
