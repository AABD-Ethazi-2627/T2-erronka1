#!/usr/bin/env bash
set -euo pipefail
# Only the isolated Compose project; no host broker or destructive operations.
docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic cnc-sensors-lab-v2 --partitions 1 --replication-factor 1
docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic cnc-sensors-smb-v1 --partitions 1 --replication-factor 1
