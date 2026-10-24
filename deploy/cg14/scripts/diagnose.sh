#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$DEPLOY_DIR"

printf '%s\n' '== Docker client/engine =='
docker version --format 'client={{.Client.Version}} server={{.Server.Version}}' 2>&1 || true
docker compose version 2>&1 || true
printf '%s\n' '== Compose validation =='
docker compose --env-file .env -f compose.yaml config --quiet 2>&1 || true
printf '%s\n' '== CG14 container =='
docker compose --env-file .env -f compose.yaml ps 2>&1 || true
printf '%s\n' '== Published ports =='
docker inspect --format '{{.Name}} {{json .NetworkSettings.Ports}}' cnc-cg14-nifi 2>&1 || true
printf '%s\n' '== Host listeners (if permitted) =='
ss -lnt 2>&1 || true
printf '%s\n' '== Host disk/memory =='
df -h "$DEPLOY_DIR" 2>&1 || true
free -h 2>&1 || true

# Deliberately omit .env, container configuration, and raw logs.
printf '%s\n' 'Diagnostics omit environment variables and log contents to avoid exposing credentials.'
