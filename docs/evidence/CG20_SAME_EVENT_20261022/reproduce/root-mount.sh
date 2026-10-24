#!/usr/bin/env bash
set -euo pipefail
root=/mnt/d/github/_local/t2-babysit-20261021/cg20-api-kibana-20261022
export TMPDIR="$root/process-temp" TEMP="$root/process-temp" TMP="$root/process-temp"
image="$root/es-posix-runtime.ext4"
target="$root/lab-01/es-posix"
test -f "$image"
test -d "$target"
if mountpoint -q "$target"; then
    echo 'Refuse to mount over an existing filesystem' >&2
    exit 1
fi
test -z "$(find "$target" -mindepth 1 -print -quit)"
mount -o loop "$image" "$target"
chown 1000:0 "$target"
chmod 1777 "$target"
findmnt -T "$target" -o SOURCE,TARGET,FSTYPE,OPTIONS
