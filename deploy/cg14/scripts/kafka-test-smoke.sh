#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd -- "$DEPLOY_DIR/../.." && pwd)"
cd "$DEPLOY_DIR"

container="cnc-cg14-kafka-test"
topic="cg14-test-raw"
fixture="$REPO_DIR/tests/fixtures/cg14/valid_event.csv"

state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"
if [[ "$state" != "healthy" ]]; then
  printf '%s\n' 'Optional test broker is not healthy. Start only it with:' >&2
  printf '%s\n' 'docker compose --env-file .env -f compose.yaml --profile kafka-test up -d kafka-test' >&2
  exit 1
fi

docker exec "$container" /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --create --if-not-exists \
  --topic "$topic" --partitions 1 --replication-factor 1 >/dev/null

expected="$(cat -- "$fixture")"
printf '%s\n' "$expected" | docker exec -i "$container" \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 --topic "$topic" >/dev/null

actual="$(docker exec "$container" /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic "$topic" --from-beginning \
  --max-messages 1 --timeout-ms 10000 2>/dev/null)"
if [[ "$actual" != "$expected" ]]; then
  printf '%s\n' 'Kafka test round-trip did not match the synthetic fixture.' >&2
  exit 1
fi

printf '%s\n' 'Kafka test broker round-trip: PASS (synthetic fixture, cg14-test-raw only).'
