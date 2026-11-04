#!/bin/sh
# The pinned upstream installer calls curl without retries. Keep its arguments,
# HTTP-status handling and checksum verification; only bound/retry transport.
exec /usr/bin/curl --retry 3 --retry-all-errors --retry-delay 2 \
  --retry-max-time 120 --connect-timeout 15 --max-time 90 "$@"
