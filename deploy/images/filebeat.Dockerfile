FROM golang:1.26.10-alpine3.23@sha256:0525c952defebc693cdaf62cdf43afa32be5a7f377e99260642ea19c240c708e AS filebeat-builder
ADD --checksum=sha256:ae4dae382249f28a53be500c0c5d5a6628677f3e65a7d35dfc148b9ad4dc0635 \
    https://github.com/elastic/beats/archive/refs/tags/v9.5.5.tar.gz \
    /tmp/beats.tar.gz
RUN mkdir /src \
    && tar -xzf /tmp/beats.tar.gz --strip-components=1 -C /src \
    && cd /src \
    && go get github.com/google/cel-go@v0.29.0 golang.org/x/net@v0.60.0 \
    && CGO_ENABLED=0 go build -trimpath -o /tmp/filebeat ./filebeat

FROM docker.elastic.co/beats/filebeat-wolfi:9.5.5@sha256:b644d58f79f2a53b46ce558efa706a51ba211e0d0f89352bfe33b3973958e3eb

USER root
RUN printf '%s\n' 'https://packages.wolfi.dev/os' > /etc/apk/repositories \
    && sed -i -E '/^(ca-certificates-bundle|curl|glibc-2[.]44|glibc-2[.]44-locale-posix|ld-linux-2[.]44|libbrotlicommon1|libbrotlidec1|libbrotlienc1|libcrypt1-2[.]44|libcurl-openssl4)=/s/=.*$//' /etc/apk/world \
    && apk upgrade --no-cache \
    && rm -f /usr/share/filebeat/filebeat
COPY --from=filebeat-builder --chown=1000:0 --chmod=0755 /tmp/filebeat /usr/share/filebeat/filebeat
USER 1000
