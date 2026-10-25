FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv
FROM cgr.dev/chainguard/wolfi-base:latest@sha256:360896efb0753a5701c48f860e17130c205eae5a264797aa3e7ea126ee2923a7
WORKDIR /app
RUN apk upgrade --no-cache \
    && apk add --no-cache python-3.11 \
    && mkdir -p /usr/local/bin \
    && ln -s /usr/bin/python3.11 /usr/local/bin/python \
    && ln -s /usr/bin/python3.11 /usr/local/bin/python3
COPY scoring/requirements.txt /app/scoring/requirements.txt
COPY --from=uv /uv /usr/local/bin/uv
RUN uv pip sync --python /usr/bin/python3.11 --system --no-cache --require-hashes --only-binary :all: /app/scoring/requirements.txt
COPY scoring /app/scoring
COPY scripts/validate_contracts.py /app/scripts/validate_contracts.py
COPY contracts /app/contracts
RUN mkdir /state && chown 65532:65532 /state
USER 65532:65532
ENV MODEL_MANIFEST=/models/manifest.json
ENV SCORING_LEDGER=/state/responses.sqlite3
CMD ["uvicorn", "scoring.score_api:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "16", "--timeout-keep-alive", "5"]
