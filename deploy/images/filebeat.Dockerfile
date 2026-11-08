FROM golang:1.26.10-alpine3.23@sha256:0525c952defebc693cdaf62cdf43afa32be5a7f377e99260642ea19c240c708e AS filebeat-builder
# Every blob/mode checked against the complete tree of the signed v9.5.5 commit.
# Avoid the non-reproducible tag archive; provenance is in filebeat-source/.
ADD --checksum=sha256:9174fdb1d926bcf717e90338538746026a44216a4690a5a1b8a30015ebe1b2bf \
    https://codeload.github.com/elastic/beats/tar.gz/b80bf8464fba72f582cefed91dd72909eb7116db \
    /tmp/beats.tar.gz
# Bound Go execution parallelism and concurrent package compilation together.
ARG GO_BUILD_JOBS=2
RUN case "$GO_BUILD_JOBS" in ''|0*|*[!0-9]*) echo "GO_BUILD_JOBS must be a positive decimal integer" >&2; exit 2;; esac \
    && export GOMAXPROCS="$GO_BUILD_JOBS" \
    && mkdir /src \
    && tar -xzf /tmp/beats.tar.gz --strip-components=1 -C /src \
    && cd /src \
    && go get github.com/google/cel-go@v0.29.0 golang.org/x/net@v0.62.0 github.com/klauspost/compress@v1.20.2 \
    && CGO_ENABLED=0 go build -p "$GO_BUILD_JOBS" -trimpath -o /tmp/filebeat ./filebeat

FROM docker.elastic.co/beats/filebeat-wolfi:9.5.5@sha256:b644d58f79f2a53b46ce558efa706a51ba211e0d0f89352bfe33b3973958e3eb AS filebeat-base

USER root
# A cheap CI target isolates the OS failure from the expensive Go build.
FROM filebeat-base AS filebeat-os
RUN id \
    && for entry in / /etc /etc/krb5.conf /tmp /var/cache/apk /lib/apk/db; do \
         if test -e "$entry"; then stat -c '%a %u:%g %n' "$entry"; else echo "absent: $entry"; fi; \
       done \
    && apk info --who-owns /etc/krb5.conf \
    && apk info -L krb5-conf
RUN printf '%s\n' 'https://packages.wolfi.dev/os' > /etc/apk/repositories \
    && sed -i -E '/^(ca-certificates-bundle|curl|glibc-2[.]44|glibc-2[.]44-locale-posix|ld-linux-2[.]44|libbrotlicommon1|libbrotlidec1|libbrotlienc1|libcrypt1-2[.]44|libcurl-openssl4)=/s/=.*$//' /etc/apk/world \
    && apk upgrade --no-cache --verbose \
    && rm -f /usr/share/filebeat/filebeat
FROM filebeat-os AS filebeat-runtime
COPY --from=filebeat-builder --chown=1000:0 --chmod=0755 /tmp/filebeat /usr/share/filebeat/filebeat
USER 1000
