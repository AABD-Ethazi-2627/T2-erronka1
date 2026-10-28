# Shared pinned uv source build: only rustls changes relative to upstream 0.13.6.
FROM rust:1.99.0-alpine@sha256:0cce0a5e0e8ba67b455257a3a02a1d99005f382748789d6464460028810f1627 AS uv-build
RUN apk add --no-cache clang cmake make musl-dev perl pkgconf patch
ADD --checksum=sha256:c2e01687fbbcb109277698ec97baca46e1547656ad580abf6d993f9c459af1c7 https://github.com/astral-sh/uv/archive/refs/tags/0.13.6.tar.gz /tmp/uv.tar.gz
RUN mkdir /src && tar -xzf /tmp/uv.tar.gz -C /src --strip-components=1
COPY deploy/images/uv-rustls.patch /tmp/uv-rustls.patch
WORKDIR /src
# Preserve embedded dependency metadata so Trivy can still audit the Rust closure.
RUN patch -p1 < /tmp/uv-rustls.patch \
    && cargo install --locked --version 0.7.7 cargo-auditable \
    && CARGO_BUILD_JOBS=4 CARGO_PROFILE_RELEASE_LTO=false CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16 \
       cargo auditable build --locked --release --package uv --bin uv --bin uvx
FROM scratch AS uv
COPY --from=uv-build /src/target/release/uv /uv
COPY --from=uv-build /src/target/release/uvx /uvx
ENTRYPOINT ["/uv"]
FROM apache/nifi:2.12.0@sha256:6f7f2840dbf178c6dd3fa13435b9b358f3be3c6fb7417de467a35a267f4d28ad AS nifi
FROM cgr.dev/chainguard/wolfi-base:latest@sha256:360896efb0753a5701c48f860e17130c205eae5a264797aa3e7ea126ee2923a7 AS jackson
ADD --checksum=sha256:8a501126a385b25841915d839508f8a66e2a0dbc8a6709d055ef3b3e852b094c https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-core/2.22.3/jackson-core-2.22.3.jar /jackson-core-2.22.3.jar
ADD --checksum=sha256:556db5439e206114346043f68d200497dc96a0bca62a360a81784092ebd0e0a9 https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-databind/2.22.3/jackson-databind-2.22.3.jar /jackson-databind-2.22.3.jar
FROM cgr.dev/chainguard/wolfi-base:latest@sha256:360896efb0753a5701c48f860e17130c205eae5a264797aa3e7ea126ee2923a7

USER root
RUN printf '%s\n' 'https://packages.wolfi.dev/os' > /etc/apk/repositories \
    && apk upgrade --no-cache \
    && apk add --no-cache bash coreutils openjdk-21-jre procps python-3.11 shadow \
    && groupadd --gid 1000 nifi \
    && useradd --uid 1000 --gid 1000 --home-dir /home/nifi --create-home --shell /bin/bash nifi

COPY --from=nifi --chown=1000:1000 /opt/nifi /opt/nifi
COPY --from=uv /uv /uvx /usr/local/bin/
RUN rm /opt/nifi/nifi-current/lib/bootstrap/jackson-core-2.22.2.jar \
        /opt/nifi/nifi-current/lib/bootstrap/jackson-databind-2.22.2.jar \
        /opt/nifi/nifi-toolkit-current/lib/jackson-core-2.22.2.jar \
        /opt/nifi/nifi-toolkit-current/lib/jackson-databind-2.22.2.jar
COPY --from=jackson --chown=1000:1000 /jackson-core-2.22.3.jar /jackson-databind-2.22.3.jar /opt/nifi/nifi-current/lib/bootstrap/
COPY --from=jackson --chown=1000:1000 /jackson-core-2.22.3.jar /jackson-databind-2.22.3.jar /opt/nifi/nifi-toolkit-current/lib/

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
