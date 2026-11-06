# CNC NiFi capability profile: preparation only

This opt-in experiment defines a positive **103 whole-NAR retain list** from the
119 actual NiFi 2.12.0 NARs in full candidate image config ID
`sha256:03f3e9a19dbce166304ec63a685c44f2da07239e5659d843c798c7f32f7012d5`
(source `12ca2fa95c0e6e94665dc75923f3cbdaa2468b24`, including the 22-target
compatible-library overlay). That identifier is a **Docker image config digest**,
not a registry manifest digest. Do not put it after a registry tag's `@` and claim
that pins a manifest. The OCI protocol below binds the distinct identities.

No default Dockerfile, Compose service, workflow, gate or dependency plan is
changed. This directory grants no runtime, model, deployment, merge or human
approval. `replacement:null`, `runtime_approved:false`,
`active_configuration_qualified:false` and `promotion_eligible:false` remain
mandatory even when preparation succeeds. A profile image remains an experimental
lab candidate and cannot be represented as a fully equivalent NiFi installation.

## Retained capability and explicit losses

`profile.json` positively names every retained and excluded NAR, its complete
source path, group/version, actual full-image SHA-256 and declared parent.
The script pins the canonical profile hash independently; caller-written JSON
cannot change the classifier or rebind source hashes. Eleven modern flow root
bundles and their 13-member declared parent closure remain. Jetty is also required
as the implicit loader root for parentless NARs. This check establishes the
structural closure, not executed classloader provenance or complete SPI closure.

All other platform/security/default/UI/unknown bundles are retained: framework,
server, Jetty, framework ZooKeeper/Kubernetes, provenance, single-user/LDAP/
Kerberos/OAuth/password encryption, SSL, content viewer, Jolt, Groovy/scripting,
native Kafka/Elasticsearch, CSV/JSON services, and all three native SMB bundles.
Every retained NAR stays byte-identical, including all nested jars, WARs,
`WEB-INF/classes`, licences, service resources and scanner metadata. Current raw
Jackson and inherited WAR findings therefore remain remediation work.

The complete current `/opt/nifi` tree outside the 16 specified whole archives is
copied: all non-NAR libraries, bootstrap/toolkit fixes, configuration defaults,
certificates, entrypoint/start scripts, Python extensions and unknown resources.
The source's `/usr/local/bin/uv` and `uvx` are copied too. Symlinks are preserved
verbatim, including image-absolute links; virtual-root resolution never follows
an image link into the host `/opt`. Ownership, permissions, modification times,
extended attributes and hardlinks are compared before/after; unsupported special
files and uncopyable metadata fail. Access times are not an identity/acceptance
field. New output must be absent and disjoint from source. Failure may leave a
private partial output without a successful `preparation.json`; never reuse it.
No source bytes are edited or deleted.

Exactly these capabilities are absent if the profile is later built:

- `nifi-amqp-nar`: native AMQP/RabbitMQ processors.
- `nifi-aws-nar`, `nifi-aws-kinesis-nar`, `nifi-aws-service-api-nar`: native AWS
  processors, Kinesis and service interfaces.
- `nifi-gcp-nar`, `nifi-gcp-services-api-nar`: native Google Cloud processors
  and service interfaces.
- `nifi-iceberg-{aws,azure,gcs,parquet-writer,processors,rest-catalog,service-api,shared}-nar`:
  NiFi Iceberg tables/catalogs/Parquet/cloud adapters.
- `nifi-kafka-service-aws-nar`, `nifi-kafka-to-s3-nar`: AWS-specific Kafka
  integration/authentication and Kafka-to-S3.

The script validates exact identifiers, not a wildcard prefix. Source-declared
modern CNC flows do not reference those 16. That does not prove absence from all
persisted/global/dynamic configurations or future operator intent. Any such use
means the profile scope is unsuitable; retain/remediate the affected extension
instead. The unchanged full image stays available as its own profile.

External SMB capture/mount/smbclient -> Filebeat -> Kafka remains outside this
pruning. Python worker CG15 Parquet/DuckDB archive is separate from NiFi Iceberg.
`ExecuteStreamCommand` continues to schedule the mounted worker; that worker owns
Kafka offsets after required archive/ES persistence. Keep native Kafka/ES/Groovy
flows too. No API, nullable/degraded semantics, Basque UI, source/model/policy
identity or AI4I current-state-only contract changes. Historical 1.25/2.0 exports
remain preserved source, not newly promised unmodified 2.12 import compatibility.

## Configuration status is deliberately unqualified

Preparation does not install captured running credentials/configuration into the
image. Fresh image defaults are preserved; own-lab persisted state is restored
separately into private volumes during acceptance.

The known sanitized own-lab capture has SHA-256
`069aa606f0a1900bc1211c80d417b218937f72b0bb11a71d409886e3dce31455`.
It records four active component types, all standard-NAR processors, eight XML
provider **declarations**, five whole-file hashes and hashed nonsecret property
values. It is not proof of selected provider classes, complete controller/
reporting/registry state, external classpaths, reflection/SPI, historical flows or
SMB. The script accepts this exact file only as
`own-lab-captured-unqualified` evidence; it never marks configuration qualified.
Do not reinterpret property hashes as semantic/provider closure.

Optional `--active-context` accepts only this explicit unknown-state object:

```json
{"status":"not-captured","components":[],"providers":[],"external_classpaths":[]}
```

Unknown/additional/missing supplied contexts or a claimed `qualified` state fail
closed before writing output. An omitted context is also recorded as unknown,
never inferred empty/unused. A future qualified-config path requires separately
reviewed implementation and real class/resource binding; this preparer contains
no approval switch or installation command.

## Local preparation without a container build

Use only an independently exported immutable source image filesystem, never a
running conf volume or a tree mixed with another image. The source NAR list and
all 119 hashes/manifests are checked; every non-NAR resource is inventoried,
preserved and compared. Whole-source provenance still requires the OCI binding
below; the tree's self-recorded hash alone does not prove image origin.

```sh
python -m scripts.nifi_runtime_profile prepare \
  --source /absolute/private/source-rootfs \
  --output /absolute/private/new-cnc-preparation \
  --profile deploy/images/nifi-patches/cnc-runtime/profile.json \
  --observed-config /absolute/private/sanitized-v2.json \
  --prepare-only
```

Outputs are `tree/`, before/after tree inventories, and `preparation.json` with
all approval/scan/runtime fields still false or not-run. Run as source owner or
root in an authorized disposable preparation environment: the tool uses
`O_NOATIME`, `chown`, no-follow metadata operations and extended attributes.
There is no permissive metadata fallback. It can reject a filesystem lacking
needed features; do not silently drop attributes to make it pass.

## Exact immutable build-context protocol (not executed here)

On the authorized VM, serialize with the common heavy-work lock and check CG32
resources (at least 6 GiB available RAM and 20 GiB disk) before a build/campaign.
Keep the existing image and evidence. An OCI-copy tool and a BuildKit builder
supporting local OCI named contexts must already be approved/available. Do not
install tooling or publish an image merely to follow these examples.

First verify the local full image's actual config ID, export it losslessly to a
fresh local OCI layout, then verify the selected **platform manifest** and every
referenced config/layer blob offline. Example with an already available Skopeo:

```sh
full_tag=cnc-guard-candidate:nifi-12ca2fa
expected_config=sha256:03f3e9a19dbce166304ec63a685c44f2da07239e5659d843c798c7f32f7012d5
test "$(docker image inspect --format '{{.Id}}' "$full_tag")" = "$expected_config"
# /absolute/private/new-cnc-full-oci must be NEW; preserve the tag and old image.
skopeo copy "docker-daemon:$full_tag" oci:/absolute/private/new-cnc-full-oci:full
# Select the amd64 platform manifest digest from the new layout's index.json.
# Substitute its ACTUAL sha256:<64 hex> value, not the config ID above.
python -m scripts.nifi_runtime_profile verify-oci \
  --layout /absolute/private/new-cnc-full-oci \
  --manifest-digest sha256:ACTUAL_PLATFORM_MANIFEST_DIGEST
```

`verify-oci` rejects an index instead of a platform manifest, a different config
ID/platform, linked blob paths or corrupt config/layer digests. Its returned
`build_context` is the exact immutable reference for the next build. Keep the
layout private, immutable and hash-verified through the build; do not substitute
a mutable Docker tag. OCI layer hashes are checked by the preparer and BuildKit;
no registry push is required. A source whose serialization changes its config ID
is rejected rather than re-labelled as 03f.

```sh
# Paste the exact build_context returned by verify-oci.
source_context=oci-layout:///absolute/private/new-cnc-full-oci@sha256:ACTUAL_PLATFORM_MANIFEST_DIGEST
docker buildx build --load \
  --build-context "nifi_full=$source_context" \
  --file deploy/images/nifi-cnc.Dockerfile --target cnc-serving \
  --tag cnc-guard-experimental:nifi-cnc-profile-v1 .
# Repeat with the SAME immutable context for the complete nested-audit target:
docker buildx build --load \
  --build-context "nifi_full=$source_context" \
  --file deploy/images/nifi-cnc.Dockerfile --target cnc-archive-audit \
  --tag cnc-guard-experimental:nifi-cnc-profile-v1-audit .
```

These commands are a prepared protocol, not evidence they ran or that this
builder accepts the named-context syntax. Record BuildKit/tool versions, actual
image IDs, source OCI manifest/config hashes, complete commands and exits.
Default final target is the same opt-in CNC serving stage; nothing references it
from the project's normal build flow.

The Dockerfile prunes only in `preparation`. The serving stage starts from the
same pinned Wolfi base as the full-image Dockerfile, with the same package names,
users, environment, entrypoint, ports and volumes. It copies only the approved
tree; it does **not** inherit any full/preparation layer. Excluded archives cannot
remain in lower serving layers. Source-image OS package versions and freshly
resolved package versions still need an actual final inventory comparison and
scan; pinned base plus matching package names is not a claim of identical OS
package bytes. Preparation reads source metadata through read-only image-stage mounts, avoiding
COPY ownership defaults as its source of truth. A final-stage inline guard
checks copied bytes/links, restores the prepared ownership/modes/xattrs/mtime and
hardlinks, and compares the full scoped inventory. This runs only inside the
disposable image build; the CLI exposes no host installation operation. These
build instructions remain unexecuted: final image/layer exports must still
independently confirm preservation, rather than relying on the build guard.

## Required acceptance before any equivalence or promotion claim

1. Verify source provenance and inspect actual OCI serving layers/rootfs; every
   excluded whole-NAR hash is absent, all 103 retained NAR hashes match, all other
   source NiFi resources, scripts, security/cert/default resources and uv match
   in bytes, permissions, ownership, links and relevant attributes. Check
   entrypoint/env/ports/volumes and OS/JRE/package identities explicitly.
2. Freeze the complete effective sanitized active flow/configuration inventory:
   selected auth/authz/state/provenance providers, root/child controller services,
   reporting tasks, parameter providers, registry clients, dynamic classpaths,
   Python/Groovy/reflection resources and implicit Jetty/inherited WARs. Bind each
   resource to actual retained class origins. Unknown/missing/excluded use fails;
   four observed standard processors do not discharge this requirement.
3. Run the **unchanged** normal and nested image gates on the actual new serving
   bytes. `cnc-archive-audit` exposes every nested archive from that serving tree
   using the existing scanner, without filtering. Link its serving stage ID/tree
   to the normal scan. Retained raw Jackson findings need compatible remediation;
   neither fewer packages nor a passing normal scan establishes green.
4. Fresh-volume bootstrap and retained-volume restore-copy tests: HTTPS trust,
   login/token and denied unauthorized access, authorization, sensitive-property
   handling, state/provenance/flowfile/content repositories, restart/recovery.
   Never publish credentials or use production/shared volumes.
5. Restore and validate all supported modern flows/native controller services,
   CSV/JSON, Kafka/ES, Groovy, HTTP, retries/DLQ; separately qualify historical
   migration. Verify real NiFi classloader, UI WAR/editor/content/provenance paths.
6. Execute mounted `ExecuteStreamCommand` worker with single offset ownership,
   API replay, archive/ES required-sink failures and recovery; run authorized CG32
   under unchanged resource limits. Verify exact event through archive/ES/scoped
   GET and Basque desktop/mobile four pages/modal, null/degraded states/refresh.
7. Run the separately authorized fresh SMB batch through external acquisition,
   Filebeat/Kafka/NiFi/API/archive/ES/GET and browser; no SMB/server mutation.
   Preserve all rubric/source/provenance/current-state semantics.
8. Independent review, protected CI and human/model/teacher acceptance remain
   separate. Do not change security exceptions, thresholds, default profiles,
   publishing/deployment triggers or approval metadata to obtain success.

Focused fixture tests (no Docker/VM/network/large archives):

```sh
python -m pytest -q tests/test_nifi_runtime_profile.py
```

They exercise drift, source immutability, symlink/path escape, metadata/hardlinks,
exact whole-extension partition, parent/implicit-Jetty closure, unknown active
context rejection, excluded-archive aliases and immutable OCI identity/layer
checks. They are preparation component tests, not a serving-image scan or NiFi
runtime acceptance.
