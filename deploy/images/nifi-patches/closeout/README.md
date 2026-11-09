# Cold API baseline capture

The default `nifi.Dockerfile` now rebuilds the full stock distribution, retaining
every NAR. Its `aws-build` stage runs the original 1,445 unit tests and checks
every production JAR entry against the runtime-tested source build. ZIP times
and Maven-generated comment timestamps are not payload identities; all classes,
resources, coordinates and dependency POMs remain checked. No test is skipped.

`fetch.py` verifies official inputs by SHA256. `build_wrappers.py` and
`build_iceberg_guava.py` first reproduce the old shaded payload byte for byte,
then replace only selected dependencies, preserving other raw ZIP records.
`assemble.py` checks the complete original archive lock before editing nested
archives. Its output records every changed occurrence; it removes no NAR.

Snappy 1.1.10.12 incorporates upstream #766. Hadoop retains only a capacity
allocation change; the original output-limit semantics are preserved. Iceberg
retains the complete updated relocated Guava library rather than minimizing
away classes required by existing consumers. This adds classes and must be
considered separately from removal of capabilities. These are explicit local
forks, not relabelled Apache releases.

See the dated evidence record for the distinction between the already scanned
and executed qualification image and the source-built Dockerfile output.

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
