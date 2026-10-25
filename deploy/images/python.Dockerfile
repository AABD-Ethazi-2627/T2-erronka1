FROM cgr.dev/chainguard/wolfi-base:latest@sha256:360896efb0753a5701c48f860e17130c205eae5a264797aa3e7ea126ee2923a7

RUN apk upgrade --no-cache \
    && apk add --no-cache python-3.11 \
    && mkdir -p /usr/local/bin \
    && ln -s /usr/bin/python3.11 /usr/local/bin/python \
    && ln -s /usr/bin/python3.11 /usr/local/bin/python3

USER 65532:65532
