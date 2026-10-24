#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"

if [[ -e "$ENV_FILE" ]]; then
  printf '%s\n' 'Secret file already exists; leaving it unchanged.'
  chmod 600 "$ENV_FILE"
  exit 0
fi

command -v openssl >/dev/null || { printf '%s\n' 'openssl is required.' >&2; exit 1; }
tmp_file="$(mktemp "$DEPLOY_DIR/.env.XXXXXX")"
trap 'rm -f -- "$tmp_file"' EXIT
username="nifi-$(openssl rand -hex 6)"
password="$(openssl rand -hex 24)"
sensitive_key="$(openssl rand -hex 32)"

cat >"$tmp_file" <<EOF
NIFI_VERSION=2.12.0
NIFI_WEB_HTTPS_PORT=8443
CG14_HOST_PORT=18443
NIFI_JVM_HEAP_INIT=1g
NIFI_JVM_HEAP_MAX=2g
NIFI_MEM_LIMIT=5g
NIFI_CPUS=3.0
SINGLE_USER_CREDENTIALS_USERNAME=$username
SINGLE_USER_CREDENTIALS_PASSWORD=$password
NIFI_SENSITIVE_PROPS_KEY=$sensitive_key
EOF
chmod 600 "$tmp_file"
mv -- "$tmp_file" "$ENV_FILE"
trap - EXIT
unset username password sensitive_key
printf 'Created %s with mode 600. Credentials were not printed.\n' "$ENV_FILE"
