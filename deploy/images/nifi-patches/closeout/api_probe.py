"""Read-only cold NiFi API smoke, run inside an isolated owned container.

Loopback TLS uses the disposable instance's self-signed certificate. This probe
does not qualify TLS trust, processor scheduling or an external integration.
Credentials and tokens never enter the returned evidence.
"""
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://localhost:8443'
CONTEXT = ssl._create_unverified_context()
ENDPOINTS = {
    'processor-types': 'processorTypes',
    'controller-service-types': 'controllerServiceTypes',
    'reporting-task-types': 'reportingTaskTypes',
    'parameter-provider-types': 'parameterProviderTypes',
    'registry-types': 'flowRegistryClientTypes',
}


def request(path, *, token=None, data=None):
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, context=CONTEXT, timeout=30) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def probe():
    checks = {}
    checks['ui'] = request('/nifi/')[0]
    checks['unauthenticated_api'] = request('/nifi-api/flow/about')[0]
    checks['invalid_credentials'] = request('/nifi-api/access/token', data={
        'username': 'cnc-closeout-invalid', 'password': 'invalid-local-control'})[0]
    status, token = request('/nifi-api/access/token', data={
        'username': os.environ['SINGLE_USER_CREDENTIALS_USERNAME'],
        'password': os.environ['SINGLE_USER_CREDENTIALS_PASSWORD']})
    checks['login'] = status
    captures = {}
    if status == 201:
        for suffix in ['about', *ENDPOINTS]:
            resource = 'controller' if suffix == 'registry-types' else 'flow'
            code, body = request('/nifi-api/' + resource + '/' + suffix, token=token)
            checks[suffix] = code
            captures[suffix] = json.loads(body) if code == 200 else {'http_status': code}
    passed = (checks['ui'] == 200 and checks['unauthenticated_api'] == 401
              and checks['invalid_credentials'] in (400, 401) and status == 201
              and all(checks.get(suffix) == 200 for suffix in ['about', *ENDPOINTS]))
    return {'schema': 1, 'checks': checks, 'captures': captures,
            'cold_api_smoke_passed': passed, 'runtime_approved': False,
            'tls_trust_qualified': False, 'processor_execution': 'not-run',
            'external_integrations': 'not-run'}


if __name__ == '__main__':
    print(json.dumps(probe(), sort_keys=True))
