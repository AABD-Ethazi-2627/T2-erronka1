FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv
FROM python:3.11.16-slim-trixie@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e
WORKDIR /app
COPY scoring/debian.sources /etc/apt/sources.list.d/debian.sources
COPY scoring/debian-security.txt /tmp/debian-security.txt
RUN apt-get update \
    && xargs -r apt-get install --only-upgrade --no-install-recommends -y < /tmp/debian-security.txt \
    && rm -rf /var/lib/apt/lists/* /tmp/debian-security.txt
COPY scoring/requirements.txt /app/scoring/requirements.txt
COPY --from=uv /uv /usr/local/bin/uv
RUN uv pip sync --system --no-cache --require-hashes --only-binary :all: /app/scoring/requirements.txt \
    && uv pip uninstall --system pip setuptools wheel \
    && rm -rf /usr/local/lib/python3.11/ensurepip
COPY scoring /app/scoring
COPY scripts/validate_contracts.py /app/scripts/validate_contracts.py
COPY contracts /app/contracts
RUN mkdir /state && chown 65532:65532 /state
USER 65532:65532
ENV MODEL_MANIFEST=/models/manifest.json
ENV SCORING_LEDGER=/state/responses.sqlite3
CMD ["uvicorn", "scoring.score_api:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "16", "--timeout-keep-alive", "5"]
