#!/bin/sh
# Use a private builder and release its memory before loading/scanning the image.
set -eu
builder=${CNC_KIBANA_BUILDER:-cnc-kibana-bounded}
archive=${1:?Usage: build_kibana_bounded.sh new-image-archive-path}
test ! -e "$archive"
# Refuse to take over any existing builder, including another active run.
if docker buildx inspect "$builder" >/dev/null 2>&1; then
    echo "Builder already exists: $builder" >&2
    exit 1
fi
docker buildx create --name "$builder" --driver docker-container \
    --driver-opt network=host \
    --driver-opt image=moby/buildkit:v0.34.2@sha256:c5f8862f52499773af85bc07695b2379ef08e8002352b0df2c4864c91d78dabe \
    --driver-opt memory=4g --driver-opt memory-swap=4g \
    --buildkitd-config deploy/images/kibana-buildkit.toml
trap 'docker buildx rm "$builder" >/dev/null' EXIT HUP INT TERM
docker buildx build --builder "$builder" --progress plain \
    --platform linux/amd64 --provenance=false \
    --file deploy/images/kibana.Dockerfile --tag cnc-guard-audit:kibana \
    --output "type=docker,dest=$archive" .
docker buildx rm "$builder"
trap - EXIT HUP INT TERM
docker load --input "$archive"
