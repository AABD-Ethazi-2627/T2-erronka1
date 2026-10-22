#!/usr/bin/env bash
# Explicit configuration: image entrypoint defaults must never choose storage.
set -euo pipefail
config=/lab/server.properties
grep -qx 'log.dirs=/var/lib/kafka/data' "$config"
grep -qx 'metadata.log.dir=/var/lib/kafka/metadata' "$config"
: "${CLUSTER_ID:?An explicit retained cluster ID is required}"
export TMPDIR=/lab/runtime TEMP=/lab/runtime TMP=/lab/runtime
export LOG_DIR=/lab/runtime/logs
export KAFKA_OPTS="-Djava.io.tmpdir=/lab/runtime -XX:-UsePerfData"
mkdir -p "$LOG_DIR" /var/lib/kafka/data /var/lib/kafka/metadata
# Check the actual bind with an actual write, including on a formatted restart.
for dir in /var/lib/kafka/data /var/lib/kafka/metadata; do
    probe=$(mktemp "$dir/.write-probe.XXXXXX")
    rm -- "$probe"
done
if [[ -f /var/lib/kafka/data/meta.properties && -f /var/lib/kafka/metadata/meta.properties ]]; then
    for dir in data metadata; do
        grep -qx "cluster.id=$CLUSTER_ID" "/var/lib/kafka/$dir/meta.properties"
    done
else
    # Partial/corrupt storage is evidence, never an invitation to reformat it.
    test -z "$(find /var/lib/kafka -mindepth 2 -print -quit)"
    /opt/kafka/bin/kafka-storage.sh format -t "$CLUSTER_ID" -c "$config"
fi
exec /opt/kafka/bin/kafka-server-start.sh "$config"
