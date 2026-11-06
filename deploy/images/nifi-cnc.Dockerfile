# OPT-IN PREPARATION CANDIDATE ONLY. No default image/workflow references this file.
# nifi_full MUST be an immutable OCI layout context verified by verify-oci;
# the expected config ID 03f... is an image config digest, not a registry manifest.
# See deploy/images/nifi-patches/cnc-runtime/README.md for the binding protocol.
FROM nifi_full AS full
FROM cgr.dev/chainguard/wolfi-base:latest@sha256:88a20e2d017bd20cdc0cb3910de603e7bea9512a6c351a8dd3c9df212ab03d73 AS preparation
USER root
RUN apk add --no-cache python-3.11
COPY scripts/nifi_runtime_profile.py /tools/nifi_runtime_profile.py
COPY deploy/images/nifi-patches/cnc-runtime/profile.json /tools/profile.json
# Read original stage metadata through immutable mounts; COPY ownership defaults
# must not become the supposed source identity.
RUN --network=none \
    --mount=type=bind,from=full,source=/opt/nifi,target=/input/opt/nifi,readonly \
    --mount=type=bind,from=full,source=/usr/local/bin/uv,target=/input/usr/local/bin/uv,readonly \
    --mount=type=bind,from=full,source=/usr/local/bin/uvx,target=/input/usr/local/bin/uvx,readonly \
    python3 /tools/nifi_runtime_profile.py prepare \
    --source /input --output /approved --profile /tools/profile.json --prepare-only

# Fresh serving ancestry: the full image/preparation layers are NOT serving layers.
# Same pinned base, packages and accounts as deploy/images/nifi.Dockerfile.
FROM cgr.dev/chainguard/wolfi-base:latest@sha256:88a20e2d017bd20cdc0cb3910de603e7bea9512a6c351a8dd3c9df212ab03d73 AS cnc-serving
USER root
RUN printf '%s\n' 'https://packages.wolfi.dev/os' > /etc/apk/repositories \
    && apk upgrade --no-cache \
    && apk add --no-cache bash coreutils openjdk-21-jre procps python-3.11 shadow \
    && groupadd --gid 1000 nifi \
    && useradd --uid 1000 --gid 1000 --home-dir /home/nifi --create-home --shell /bin/bash nifi
COPY --from=preparation /approved/tree/opt/nifi /opt/nifi
COPY --from=preparation /approved/tree/usr/local/bin/ /usr/local/bin/
# Restore and verify original metadata after COPY, inside this disposable build
# stage only. There is deliberately no host installation command in the CLI.
RUN --network=none \
    --mount=type=bind,from=preparation,source=/approved,target=/proof,readonly \
    --mount=type=bind,source=scripts/nifi_runtime_profile.py,target=/tools/nifi_runtime_profile.py,readonly \
    python3 - <<'PY'
import importlib.util
import os
from pathlib import Path
spec = importlib.util.spec_from_file_location('cnc_profile', '/tools/nifi_runtime_profile.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
rows = p.load('/proof/prepared-tree.json')
proof = p.load('/proof/preparation.json')
p.require(proof['prepared_tree_sha256'] == p.canonical_sha256(rows), 'prepared metadata mismatch')
current = p.snapshot(Path('/'))
p.require(set(current) == set(rows), 'serving paths changed during COPY')
for name, row in rows.items():
    p.relative(name)
    p.require(p.in_scope(name) or name in ('opt', 'usr', 'usr/local', 'usr/local/bin'), 'unexpected metadata scope')
    p.require(current[name]['kind'] == row['kind'], 'serving path kind changed')
    if row['kind'] == 'file':
        p.require(current[name]['sha256'] == row['sha256'], 'serving bytes changed during COPY')
        if 'hardlink_to' in row:
            target = row['hardlink_to']
            p.relative(target)
            p.require(target in rows and rows[target]['kind'] == 'file' and rows[target]['sha256'] == row['sha256'], 'invalid prepared hardlink')
            os.unlink('/' + name)
            os.link('/' + target, '/' + name)
    elif row['kind'] == 'symlink':
        p.require(current[name]['target'] == row['target'], 'serving link changed during COPY')
for name in sorted(rows, key=lambda x: (len(Path(x).parts), x), reverse=True):
    p._copy_metadata(Path('/') / name, rows[name])
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
