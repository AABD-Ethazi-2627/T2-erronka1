FROM docker.elastic.co/kibana/kibana-wolfi:9.5.5@sha256:46b0a3adf85186f9153fbd322e55ea8f70bc4039dcd55d58826fc1caa372dee5 AS patches

USER root
WORKDIR /patches
RUN printf '%s\n' 'https://packages.wolfi.dev/os' > /etc/apk/repositories \
    && apk add --no-cache npm zip
COPY deploy/images/kibana-patches/package.json deploy/images/kibana-patches/package-lock.json ./
RUN npm ci --ignore-scripts --audit=false
COPY deploy/images/kibana-patches/audit-glob-consumers.js ./
RUN node --max-old-space-size=256 audit-glob-consumers.js /usr/share/kibana --check-legacy-migration > glob-importers.json
COPY deploy/images/kibana-patches/apply-deepmerge-patch.js deploy/images/kibana-patches/test-deepmerge-patch.js ./
RUN node apply-deepmerge-patch.js && node test-deepmerge-patch.js
COPY deploy/images/kibana-patches/apply-extract-zip-patch.js deploy/images/kibana-patches/test-extract-zip-patch.js ./
RUN node apply-extract-zip-patch.js \
    && mkdir -p /tmp/fixture \
    && ln -s ../../outside /tmp/fixture/escape \
    && cd /tmp/fixture \
    && zip -y /tmp/symlink.zip escape \
    && node /patches/test-extract-zip-patch.js
COPY deploy/images/kibana-patches/apply-minimatch-patch.js deploy/images/kibana-patches/test-minimatch-limits.js ./
RUN node apply-minimatch-patch.js \
    && node --max-old-space-size=384 test-minimatch-limits.js /patches/node_modules/minimatch-v10

FROM patches AS glob-migration
WORKDIR /glob-migration
COPY deploy/images/kibana-patches/glob-migration/package.json deploy/images/kibana-patches/glob-migration/package-lock.json ./
# Keep the upgraded Glob dependency closure nested; root Minimatch retains its API.
RUN npm ci --ignore-scripts --audit=false --install-strategy=nested

FROM docker.elastic.co/kibana/kibana-wolfi:9.5.5@sha256:46b0a3adf85186f9153fbd322e55ea8f70bc4039dcd55d58826fc1caa372dee5

USER root
RUN printf '%s\n' 'https://packages.wolfi.dev/os' > /etc/apk/repositories \
    && sed -i -E '/^(ca-certificates|ca-certificates-bundle|curl|glibc-2[.]44|glibc-2[.]44-locale-posix|ld-linux-2[.]44|libbrotlicommon1|libbrotlidec1|libcrypt1-2[.]44|libcurl-openssl4)=/s/=.*$//' /etc/apk/world \
    && apk upgrade --no-cache \
    && rm -rf /usr/share/kibana/node_modules/zod-to-json-schema/dist-test-v3 \
        /usr/share/kibana/node_modules/zod-to-json-schema/dist-test-v4
# Remove the old package directories so removed upstream files cannot survive COPY.
RUN rm -rf /usr/share/kibana/node_modules/decode-uri-component \
    /usr/share/kibana/node_modules/systeminformation \
    /usr/share/kibana/node_modules/re2js \
    /usr/share/kibana/node_modules/joi \
    /usr/share/kibana/node_modules/@hapi/content \
    /usr/share/kibana/node_modules/@hono/node-server \
    /usr/share/kibana/node_modules/glob \
    /usr/share/kibana/node_modules/rimraf \
    /usr/share/kibana/node_modules/minimatch
COPY --from=patches /patches/node_modules/deepmerge-patched /usr/share/kibana/node_modules/deepmerge
COPY --from=patches /patches/node_modules/qs-patched /usr/share/kibana/node_modules/qs
COPY --from=patches /patches/node_modules/ai-provider-utils /usr/share/kibana/node_modules/@ai-sdk/provider-utils
COPY --from=patches /patches/node_modules/grpc-js /usr/share/kibana/node_modules/@grpc/grpc-js
COPY --from=patches /patches/node_modules/mcp-sdk /usr/share/kibana/node_modules/@modelcontextprotocol/sdk
COPY --from=patches /patches/node_modules/otel-cassandra /usr/share/kibana/node_modules/@opentelemetry/instrumentation-cassandra-driver
COPY --from=patches /patches/node_modules/otel-knex /usr/share/kibana/node_modules/@opentelemetry/instrumentation-knex
COPY --from=patches /patches/node_modules/otel-mongoose /usr/share/kibana/node_modules/@opentelemetry/instrumentation-mongoose
COPY --from=patches /patches/node_modules/otel-mysql /usr/share/kibana/node_modules/@opentelemetry/instrumentation-mysql
COPY --from=patches /patches/node_modules/otel-mysql2 /usr/share/kibana/node_modules/@opentelemetry/instrumentation-mysql2
COPY --from=patches /patches/node_modules/otel-oracledb /usr/share/kibana/node_modules/@opentelemetry/instrumentation-oracledb
COPY --from=patches /patches/node_modules/otel-pg /usr/share/kibana/node_modules/@opentelemetry/instrumentation-pg
COPY --from=patches /patches/node_modules/otel-tedious /usr/share/kibana/node_modules/@opentelemetry/instrumentation-tedious
COPY --from=patches /patches/node_modules/axios-patched /usr/share/kibana/node_modules/axios
COPY --from=patches /patches/node_modules/basic-ftp-patched /usr/share/kibana/node_modules/basic-ftp
COPY --from=patches /patches/node_modules/body-parser-v1 /usr/share/kibana/node_modules/@a2a-js/sdk/node_modules/body-parser
COPY --from=patches /patches/node_modules/body-parser-v2 /usr/share/kibana/node_modules/body-parser
COPY --from=patches /patches/node_modules/brace-expansion-v1 /usr/share/kibana/node_modules/del/node_modules/brace-expansion
COPY --from=patches /patches/node_modules/brace-expansion-v2 /usr/share/kibana/node_modules/brace-expansion
COPY --from=patches /patches/node_modules/d3-color-patched /usr/share/kibana/node_modules/d3-scale/node_modules/d3-color
COPY --from=patches /patches/node_modules/decode-uri-component-patched /usr/share/kibana/node_modules/decode-uri-component
COPY --from=patches /patches/node_modules/dompurify-patched /usr/share/kibana/node_modules/dompurify
COPY --from=patches /patches/node_modules/extract-zip-patched /usr/share/kibana/node_modules/extract-zip
COPY --from=patches /patches/node_modules/fast-uri-patched /usr/share/kibana/node_modules/fast-uri
COPY --from=patches /patches/node_modules/fast-xml-parser-patched /usr/share/kibana/node_modules/fast-xml-parser
COPY --from=patches /patches/node_modules/follow-redirects-patched /usr/share/kibana/node_modules/follow-redirects
COPY --from=patches /patches/node_modules/handlebars-patched /usr/share/kibana/node_modules/handlebars
COPY --from=patches /patches/node_modules/hono-patched /usr/share/kibana/node_modules/hono
COPY --from=patches /patches/node_modules/ip-address-patched /usr/share/kibana/node_modules/ip-address
COPY --from=patches /patches/node_modules/markdown-it-patched /usr/share/kibana/node_modules/markdown-it
COPY --from=patches /patches/node_modules/nodemailer-patched /usr/share/kibana/node_modules/nodemailer
COPY --from=patches /patches/node_modules/piscina-patched /usr/share/kibana/node_modules/piscina
COPY --from=patches /patches/node_modules/prismjs-patched /usr/share/kibana/node_modules/prismjs
COPY --from=patches /patches/node_modules/smol-toml-patched /usr/share/kibana/node_modules/smol-toml
COPY --from=patches /patches/node_modules/undici-v6 /usr/share/kibana/node_modules/@elastic/opamp-client-node/node_modules/undici
COPY --from=patches /patches/node_modules/undici-v7 /usr/share/kibana/node_modules/undici
COPY --from=patches /patches/node_modules/zod-patched /usr/share/kibana/node_modules/zod
COPY --from=patches /patches/node_modules/systeminformation-patched /usr/share/kibana/node_modules/systeminformation
COPY --from=patches /patches/node_modules/re2js-patched /usr/share/kibana/node_modules/re2js
COPY --from=patches /patches/node_modules/joi-patched /usr/share/kibana/node_modules/joi
COPY --from=patches /patches/node_modules/hapi-content-patched /usr/share/kibana/node_modules/@hapi/content
COPY --from=patches /patches/node_modules/hono-node-server-patched /usr/share/kibana/node_modules/@hono/node-server
COPY --from=glob-migration /glob-migration/node_modules/glob /usr/share/kibana/node_modules/glob
COPY --from=glob-migration /glob-migration/node_modules/rimraf /usr/share/kibana/node_modules/rimraf
COPY --from=patches /patches/node_modules/minimatch-v10 /usr/share/kibana/node_modules/minimatch
# This copy needs brace-expansion 5 and its balanced-match 4, not the root v2 copy.
COPY --from=patches /patches/node_modules/brace-expansion /usr/share/kibana/node_modules/minimatch/node_modules/brace-expansion
RUN rm -rf /usr/share/kibana/node_modules/node-forge
# Replace actual upstream library and dist bytes; do not reapply the 1.4.0 backport.
COPY --from=patches /patches/node_modules/node-forge-patched /usr/share/kibana/node_modules/node-forge
COPY deploy/images/kibana-patches/test-node-forge-patch.js deploy/images/kibana-patches/test-node-forge-chain.js deploy/images/kibana-patches/test-follow-redirects.js deploy/images/kibana-patches/test-same-line-updates.js deploy/images/kibana-patches/test-hono-node-server.js /tmp/
COPY deploy/images/kibana-patches/test-glob-migration.js deploy/images/kibana-patches/test-minimatch-limits.js deploy/images/kibana-patches/test-minimatch3-applicability.js /tmp/
RUN /usr/share/kibana/node/default/bin/node /tmp/test-node-forge-patch.js \
    && /usr/share/kibana/node/default/bin/node /tmp/test-node-forge-chain.js \
    && /usr/share/kibana/node/default/bin/node /tmp/test-follow-redirects.js \
    && /usr/share/kibana/node/default/bin/node /tmp/test-same-line-updates.js \
    && /usr/share/kibana/node/default/bin/node /tmp/test-hono-node-server.js \
    && /usr/share/kibana/node/default/bin/node --max-old-space-size=256 /tmp/test-glob-migration.js \
    && /usr/share/kibana/node/default/bin/node --max-old-space-size=384 /tmp/test-minimatch-limits.js \
    && /usr/share/kibana/node/default/bin/node --max-old-space-size=128 /tmp/test-minimatch3-applicability.js \
    && rm /tmp/test-node-forge-patch.js /tmp/test-node-forge-chain.js /tmp/test-follow-redirects.js /tmp/test-same-line-updates.js /tmp/test-hono-node-server.js /tmp/test-glob-migration.js /tmp/test-minimatch-limits.js /tmp/test-minimatch3-applicability.js
USER 1000
