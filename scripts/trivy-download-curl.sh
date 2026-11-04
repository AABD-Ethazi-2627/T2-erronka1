#!/bin/sh
# Bound release-download transport. Callers retain HTTP status and checksum checks.
exec /usr/bin/curl --retry 3 --retry-all-errors --retry-delay 2 \
  --retry-max-time 120 --connect-timeout 15 --max-time 90 "$@"
