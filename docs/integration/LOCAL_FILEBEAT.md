# Reproduce the bounded Filebeat producer

This is an isolated local CSV → vendor Filebeat → candidate Kafka rehearsal.
It does not contact SMB or demonstrate the patched final Filebeat image. Run from
the repository root with the locked backend `.venv`, Docker, `socat`, and the
already built `cnc-guard-local:kafka` image. Build that image serially using
`deploy/images/kafka.Dockerfile` if absent. Do not run alongside image builds on
a constrained host. This runbook was reconstructed from the retained container
configuration and capture after the first rehearsal; execute a new rehearsal to
validate these exact instructions. Never overwrite the previous evidence.

The commands below expect host UID 1000, matching the container's non-root user.
They create fresh names and preserve every container, registry and broker log on
stop. Port 19094 must be free; do not stop another service to claim it.

```sh
test "$(id -u)" = 1000
export CNC_LAB_ROOT="$(mktemp -d "$HOME/.cache/cnc-ingress-XXXXXX")"
export CNC_LAB_TOKEN="$(.venv/bin/python -c 'import uuid; print(uuid.uuid4().hex)')"
export CNC_LAB_NETWORK="cnc-local-$CNC_LAB_TOKEN"
export CNC_LAB_KAFKA="cnc-local-kafka-$CNC_LAB_TOKEN"
export CNC_LAB_FILEBEAT="cnc-local-filebeat-$CNC_LAB_TOKEN"
export CNC_LAB_TOPIC="cnc-local-raw-$CNC_LAB_TOKEN"
.venv/bin/python - <<'PY'
import hashlib, json, os
from datetime import UTC, datetime
from pathlib import Path
from scripts.cg32_load import HEADER
from scripts.integration_worker_local import fixture_row
root = Path(os.environ['CNC_LAB_ROOT'])
for name in ('input', 'unused-smb', 'filebeat-data', 'kafka'):
    (root / name).mkdir()
line = fixture_row(datetime.now(UTC).isoformat(timespec='milliseconds').replace('+00:00','Z')).rstrip(b'\n')
header = (HEADER + '\n').encode()
payload = header + line + b'\n'
assert len(header) == 164 and len(payload) >= 228
(root / 'input/sample.csv').write_bytes(payload)
(root / 'expected-message.bin').write_bytes(line)
# Filebeat fingerprint serializes the field name as well as its value.
key = hashlib.sha256(b'|message|' + line + b'|').hexdigest() + ':' + str(len(header))
(root / 'expected-key.bin').write_bytes(key.encode())
config = Path('filebeat/filebeat.yml').read_text()
assert "hosts: ['kafka:9092']" in config and 'topic: cnc-sensors-lab-v2' in config
config = config.replace("hosts: ['kafka:9092']", "hosts: ['kafka:19092']").replace('topic: cnc-sensors-lab-v2', 'topic: ' + os.environ['CNC_LAB_TOPIC'])
(root / 'filebeat.yml').write_text(config)
(root / 'state.json').write_text(json.dumps({
    'topic': os.environ['CNC_LAB_TOPIC'],
    'namespace': 'local-kafka-' + os.environ['CNC_LAB_TOKEN'],
    'bootstrap': '127.0.0.1:19094',
    'network': os.environ['CNC_LAB_NETWORK'],
    'kafka_container': os.environ['CNC_LAB_KAFKA'],
    'filebeat_container': os.environ['CNC_LAB_FILEBEAT'],
    'input_sha256': hashlib.sha256(payload).hexdigest(),
    'expected_payload_sha256': hashlib.sha256(line).hexdigest(),
    'expected_key': key,
    'filebeat_config_sha256': hashlib.sha256(config.encode()).hexdigest(),
    'producer_kind': 'digest-pinned vendor Filebeat; not patched final image'
}, indent=2))
PY
docker network create --internal "$CNC_LAB_NETWORK"
docker run -d --name "$CNC_LAB_KAFKA" --network "$CNC_LAB_NETWORK" --network-alias kafka \
  --memory 768m --memory-swap 768m --cpus 1.5 --pids-limit 512 \
  --cap-drop ALL --security-opt no-new-privileges --user 1000 \
  --mount "type=bind,src=$CNC_LAB_ROOT/kafka,dst=/var/lib/kafka/data" \
  -e KAFKA_NODE_ID=1 -e KAFKA_PROCESS_ROLES=broker,controller \
  -e KAFKA_LISTENERS=PLAINTEXT://:19092,HOST://:9092,CONTROLLER://:19093 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:19092,HOST://127.0.0.1:19094 \
  -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,HOST:PLAINTEXT \
  -e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER \
  -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka:19093 \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 -e KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1 \
  -e KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1 -e KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS=0 \
  -e KAFKA_AUTO_CREATE_TOPICS_ENABLE=false -e KAFKA_LOG_DIRS=/var/lib/kafka/data \
  -e 'KAFKA_HEAP_OPTS=-Xms256m -Xmx256m' cnc-guard-local:kafka
docker inspect "$CNC_LAB_KAFKA" --format '{{.Image}}' > "$CNC_LAB_ROOT/kafka-image-id.txt"
```

In a second terminal, use the `CNC_LAB_KAFKA` name printed/saved above to create
the host-only bridge. Docker's internal network stays internal. Leave this
command in the foreground and stop it with Ctrl-C after the consumer rehearsal.

```sh
export CNC_LAB_KAFKA=cnc-local-kafka-REPLACE_WITH_THIS_RUN_TOKEN
CNC_LAB_BROKER_IP="$(docker inspect "$CNC_LAB_KAFKA" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')"
test -n "$CNC_LAB_BROKER_IP"
socat TCP-LISTEN:19094,bind=127.0.0.1,reuseaddr,fork "TCP:$CNC_LAB_BROKER_IP:9092"
```

Back in the first terminal, create exactly one new partition. If the broker is not
ready, this bounded operation fails; inspect its log, then retry creation only
after verifying that this run's topic does not already exist. Never delete a topic
to make this command pass.

```sh
.venv/bin/python - <<'PY'
import os
from kafka.admin import KafkaAdminClient, NewTopic
admin = KafkaAdminClient(bootstrap_servers='127.0.0.1:19094', api_version=(3,7), request_timeout_ms=15000)
try:
    admin.create_topics([NewTopic(os.environ['CNC_LAB_TOPIC'], 1, 1)], timeout_ms=15000)
finally:
    admin.close()
PY
docker run -d --name "$CNC_LAB_FILEBEAT" --network "$CNC_LAB_NETWORK" \
  --memory 256m --memory-swap 256m --cpus .5 --pids-limit 256 \
  --cap-drop ALL --security-opt no-new-privileges --user 1000 \
  --mount "type=bind,src=$CNC_LAB_ROOT/filebeat.yml,dst=/filebeat.yml,readonly" \
  --mount "type=bind,src=$CNC_LAB_ROOT/input,dst=/mnt/cnc-stream,readonly" \
  --mount "type=bind,src=$CNC_LAB_ROOT/unused-smb,dst=/mnt/cnc-smb,readonly" \
  --mount "type=bind,src=$CNC_LAB_ROOT/filebeat-data,dst=/state" \
  docker.elastic.co/beats/filebeat-wolfi:9.5.5@sha256:b644d58f79f2a53b46ce558efa706a51ba211e0d0f89352bfe33b3973958e3eb \
  filebeat -e -c /filebeat.yml --path.data /state
.venv/bin/python - <<'PY'
import json, os, time
from pathlib import Path
from kafka import TopicPartition
from scripts.integration_kafka_worker_local import consumer, capture_record
root = Path(os.environ['CNC_LAB_ROOT'])
topic = os.environ['CNC_LAB_TOPIC']
reader = consumer('127.0.0.1:19094')
try:
    tp = TopicPartition(topic, 0)
    deadline = time.monotonic() + 60
    while reader.end_offsets([tp], timeout_ms=15000)[tp] == 0:
        if time.monotonic() >= deadline:
            raise TimeoutError('No Filebeat record within capture budget')
        time.sleep(.5)
    raw, key, record = capture_record(reader, topic)
    (root / 'captured.bin').write_bytes(raw)
    (root / 'captured.key.bin').write_bytes(key or b'')
    (root / 'captured.json').write_text(json.dumps(record, indent=2))
    assert raw == (root / 'expected-message.bin').read_bytes(), 'payload differs'
    assert key == (root / 'expected-key.bin').read_bytes(), 'fingerprint/offset key differs'
finally:
    reader.close(autocommit=False)
PY
docker logs "$CNC_LAB_FILEBEAT" > "$CNC_LAB_ROOT/filebeat.log" 2>&1
docker stop "$CNC_LAB_FILEBEAT"
docker logs "$CNC_LAB_FILEBEAT" > "$CNC_LAB_ROOT/filebeat-stopped.log" 2>&1
```

The reader creates no group and commits nothing. Check Filebeat's retained final
monitoring for one published/acked event. `captured.json` is a broker observation,
not proof of producer identity alone: compare the payload, field-aware fingerprint
and byte offset, container image and Filebeat log together. The capture has no
`origin` success label to substitute for these checks.

Keep Kafka and its bridge running for [LOCAL_KAFKA.md](LOCAL_KAFKA.md), using the
namespace/topic in this run's `state.json`. Run the worker against a separately
owned loopback ES instance. Afterwards, stop only this broker and preserve state:

```sh
docker logs "$CNC_LAB_KAFKA" > "$CNC_LAB_ROOT/kafka.log" 2>&1
docker stop "$CNC_LAB_KAFKA"
```
