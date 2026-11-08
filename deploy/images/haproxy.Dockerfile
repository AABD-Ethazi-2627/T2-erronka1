FROM haproxy:3.4.7-alpine@sha256:5312d37032c079c4937d45ef63758852434351f3b425a3703521fd999837abcf

# The current official image predates Alpine's zlib security release.
USER root
RUN apk upgrade --no-cache && apk add --no-cache zlib=1.4-r0
USER haproxy
