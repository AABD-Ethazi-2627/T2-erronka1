# Cold API baseline capture

Run `smoke.py --container cnc-closeout-nifi-NAME --output /absolute/new-output`
using Python3.12 on the Docker client host. The container must be owned by this
campaign, running with `--network none`, HTTPS8443 reachable on its loopback,
Python3 available and disposable single-user credentials in its environment.
No ports or user volumes are needed. The tool reads only the API and Docker
metadata; credentials and JWTs remain inside the container and are not recorded.

The probe checks UI/login, rejects anonymous API and wrong-password access,
captures all five extension type families, and checks modern declared flow
type/bundle identities against those live registries. Service interface
requirements use the live implementation's `controllerServiceApis`, not an
invented instantiable interface. Registry types come from
`/controller/registry-types`, verified against official NiFi2.12 source/runtime.
The result identifies the actual Docker daemon, immutable image config,
container, resource limits and source hashes.

This is cold discovery and authentication evidence. It does not restore state,
schedule processors, validate certificate trust, test SMB/Kafka/Elasticsearch,
or grant runtime/production approval. Loopback TLS uses the disposable instance's
self-signed certificate; this is explicit in `tls_trust_qualified:false`.
Run the separate established integration/security gates for those properties.
