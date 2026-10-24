FROM python:3.13.17-alpine3.23@sha256:85c3e958f9448b4c75069957f1f6a3be5325e8ea7ad1f205142fc9d023d0531b

RUN python -m pip uninstall --yes pip setuptools wheel \
    && rm -rf /usr/local/lib/python3.13/ensurepip
