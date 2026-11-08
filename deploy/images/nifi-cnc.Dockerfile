# OPT-IN PREPARATION CANDIDATE ONLY. No default image/workflow references this file.
# nifi_full MUST be an immutable OCI layout context verified by verify-oci;
# the expected config ID 03f... is an image config digest, not a registry manifest.
# See deploy/images/nifi-patches/cnc-runtime/README.md for the binding protocol.
FROM nifi_full AS full
FROM cgr.dev/chainguard/wolfi-base:latest@sha256:88a20e2d017bd20cdc0cb3910de603e7bea9512a6c351a8dd3c9df212ab03d73 AS preparation
USER root
RUN apk add --no-cache python-3.11
COPY scripts/nifi_runtime_profile.py /tools/nifi_runtime_profile.py
COPY deploy/images/nifi-patches/cnc-runtime/ /tools/cnc-runtime/
COPY nifi-flows/ /flow-input/nifi-flows/
COPY deploy/cg14/restore-inventory.json /flow-input/deploy/cg14/restore-inventory.json
# Read original stage metadata through immutable mounts; COPY ownership defaults
# must not become the supposed source identity.
RUN --network=none \
    --mount=type=bind,from=full,source=/opt/nifi,target=/input/opt/nifi,readonly \
    --mount=type=bind,from=full,source=/usr/local/bin/uv,target=/input/usr/local/bin/uv,readonly \
    --mount=type=bind,from=full,source=/usr/local/bin/uvx,target=/input/usr/local/bin/uvx,readonly \
    python3 /tools/nifi_runtime_profile.py prepare \
    --source /input --output /approved --profile /tools/cnc-runtime/profile.json \
    --flow-root /flow-input --prepare-only

# Fresh serving ancestry: the full image/preparation layers are NOT serving layers.
# Same pinned base, packages and accounts as deploy/images/nifi.Dockerfile.
FROM cgr.dev/chainguard/wolfi-base:latest@sha256:88a20e2d017bd20cdc0cb3910de603e7bea9512a6c351a8dd3c9df212ab03d73 AS cnc-serving
USER root
RUN printf '%s\n' 'https://packages.wolfi.dev/os' > /etc/apk/repositories \
    && apk upgrade --no-cache \
    && apk add --no-cache bash coreutils openjdk-21-jre procps python-3.11 shadow \
    && groupadd --gid 1000 nifi \
    && useradd --uid 1000 --gid 1000 --home-dir /home/nifi --create-home --shell /bin/bash nifi
# One write layer for bytes and metadata. Only scope entries are restored;
# opt/usr/usr/local/usr/local/bin belong to the fresh OS and are not source stubs.
RUN --network=none \
    --mount=type=bind,from=preparation,source=/approved,target=/proof,readonly \
    --mount=type=bind,source=scripts/nifi_runtime_profile.py,target=/tools/nifi_runtime_profile.py,readonly \
    python3 - <<'PY'
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('cnc_profile', '/tools/nifi_runtime_profile.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
rows = p.load('/proof/prepared-tree.json')
proof = p.load('/proof/preparation.json')
p.require(proof['prepared_tree_sha256'] == p.canonical_sha256(rows), 'prepared metadata mismatch')
p.require(proof['source_binding'] == 'independently-frozen-cold-scope-baseline', 'source binding missing')
p.require(proof['bound_source_image_config_id'] == p.SOURCE_IMAGE_ID, 'bound source identity mismatch')
p.require(p.snapshot(Path('/proof/tree')) == rows, 'prepared bytes or metadata changed')
p.materialize_scopes(Path('/proof/tree'), Path('/'), rows)
p.require(p.snapshot(Path('/')) == rows, 'serving metadata differs from prepared source')
PY
COPY --from=preparation /approved/preparation.json /usr/share/cnc-guard/cnc-runtime/preparation.json
COPY --from=preparation /approved/source-tree.json /approved/prepared-tree.json /usr/share/cnc-guard/cnc-runtime/
COPY deploy/images/nifi-patches/cnc-runtime/profile.json /usr/share/cnc-guard/cnc-runtime/profile.json
LABEL org.cnc-guard.runtime-approved="false" \
      org.cnc-guard.capability-profile="cnc-serving-conservative-v1-preparation-only"
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk \
    PATH=/usr/lib/jvm/java-21-openjdk/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    NIFI_BASE_DIR=/opt/nifi \
    NIFI_HOME=/opt/nifi/nifi-current \
    NIFI_TOOLKIT_HOME=/opt/nifi/nifi-toolkit-current \
    NIFI_PID_DIR=/opt/nifi/nifi-current/run \
    NIFI_LOG_DIR=/opt/nifi/nifi-current/logs
WORKDIR /opt/nifi/nifi-current
USER 1000
EXPOSE 8000 8443 10000
VOLUME ["/opt/nifi/nifi-current/conf", "/opt/nifi/nifi-current/content_repository", "/opt/nifi/nifi-current/database_repository", "/opt/nifi/nifi-current/flowfile_repository", "/opt/nifi/nifi-current/logs", "/opt/nifi/nifi-current/nar_extensions", "/opt/nifi/nifi-current/provenance_repository", "/opt/nifi/nifi-current/python_extensions", "/opt/nifi/nifi-current/state"]
ENTRYPOINT ["../scripts/start.sh"]

# Expose ALL nested archives from this same serving tree, with unchanged scanner.
FROM cnc-serving AS cnc-archive-audit
USER root
COPY scripts/expose_nested_jars.py /tmp/expose_nested_jars.py
RUN python3 /tmp/expose_nested_jars.py /opt/nifi /usr/share/cnc-guard/nested-jars
USER 1000

FROM cnc-serving AS final
