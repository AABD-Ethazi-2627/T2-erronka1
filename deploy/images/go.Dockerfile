FROM golang:1.26.10-alpine3.23@sha256:0525c952defebc693cdaf62cdf43afa32be5a7f377e99260642ea19c240c708e

# Keep the builder pin shared with Filebeat; audit the refreshed auxiliary image.
RUN apk upgrade --no-cache && apk add --no-cache zlib=1.4-r0
