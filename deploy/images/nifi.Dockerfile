FROM apache/nifi:2.12.0@sha256:6f7f2840dbf178c6dd3fa13435b9b358f3be3c6fb7417de467a35a267f4d28ad AS nifi
FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv
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
