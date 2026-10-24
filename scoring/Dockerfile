FROM python:3.11-slim
WORKDIR /app
COPY scoring/requirements.txt /app/scoring/requirements.txt
RUN pip install --no-cache-dir -r /app/scoring/requirements.txt
COPY scoring /app/scoring
COPY scripts/validate_contracts.py /app/scripts/validate_contracts.py
COPY contracts /app/contracts
RUN mkdir /state && chown 65532:65532 /state
USER 65532:65532
ENV MODEL_MANIFEST=/models/manifest.json
ENV SCORING_LEDGER=/state/responses.sqlite3
CMD ["uvicorn", "scoring.score_api:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "16", "--timeout-keep-alive", "5"]
