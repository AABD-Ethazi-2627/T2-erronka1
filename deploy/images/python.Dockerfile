FROM cgr.dev/chainguard/wolfi-base:latest@sha256:88a20e2d017bd20cdc0cb3910de603e7bea9512a6c351a8dd3c9df212ab03d73

RUN apk upgrade --no-cache \
    && apk add --no-cache python-3.11 \
    && mkdir -p /usr/local/bin \
    && ln -s /usr/bin/python3.11 /usr/local/bin/python \
    && ln -s /usr/bin/python3.11 /usr/local/bin/python3

USER 65532:65532
