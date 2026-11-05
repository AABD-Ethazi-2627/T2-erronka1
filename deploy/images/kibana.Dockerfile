FROM docker.elastic.co/kibana/kibana-wolfi:9.5.5@sha256:46b0a3adf85186f9153fbd322e55ea8f70bc4039dcd55d58826fc1caa372dee5 AS patches

USER root
WORKDIR /patches
RUN printf '%s\n' 'https://packages.wolfi.dev/os' > /etc/apk/repositories \
    && apk add --no-cache npm zip
COPY deploy/images/kibana-patches/package.json deploy/images/kibana-patches/package-lock.json ./
RUN npm ci --ignore-scripts --audit=false
COPY deploy/images/kibana-patches/audit-glob-consumers.js ./
RUN node --max-old-space-size=256 audit-glob-consumers.js /usr/share/kibana --check-legacy-migration > glob-importers.json
COPY deploy/images/kibana-patches/del-inventory.cjs deploy/images/kibana-patches/del-base-inventory.json deploy/images/kibana-patches/prepare-del-migration.cjs ./
# Exact incoming tree guard includes CJS/ESM, bundles, compressed assets and metadata.
RUN /usr/share/kibana/node/default/bin/node --max-old-space-size=256 prepare-del-migration.cjs /usr/share/kibana /patches/del-patched > del-preparation.json
COPY deploy/images/kibana-patches/apply-deepmerge-patch.js deploy/images/kibana-patches/test-deepmerge-patch.js ./
RUN node apply-deepmerge-patch.js && node test-deepmerge-patch.js
COPY deploy/images/kibana-patches/apply-extract-zip-patch.js deploy/images/kibana-patches/test-extract-zip-patch.js ./
RUN node apply-extract-zip-patch.js \
    && mkdir -p /tmp/fixture \
    && ln -s ../../outside /tmp/fixture/escape \
    && cd /tmp/fixture \
    && zip -y /tmp/symlink.zip escape \
    && node /patches/test-extract-zip-patch.js
# Historical MM10 backport drivers remain in source; no fork is copied to runtime.

FROM patches AS minimatch-migration
WORKDIR /minimatch-migration
COPY deploy/images/kibana-patches/minimatch-migration/package.json deploy/images/kibana-patches/minimatch-migration/package-lock.json ./
RUN npm ci --ignore-scripts --audit=false --install-strategy=nested
COPY deploy/images/kibana-patches/mm11-migration.cjs deploy/images/kibana-patches/mm11-inputs.json deploy/images/kibana-patches/mm11-official-files.json deploy/images/kibana-patches/mm11-output-files.json deploy/images/kibana-patches/install-del-migration.cjs deploy/images/kibana-patches/del-output-hashes.json /patches/
# Both preparations inspect the unchanged original base; del was prepared first.
RUN /usr/share/kibana/node/default/bin/node --max-old-space-size=256 /patches/mm11-migration.cjs prepare /usr/share/kibana /minimatch-migration/node_modules/minimatch /patches/mm11-prepared /patches/del-patched.modules.yaml > /patches/mm11-preparation.json

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
# Verify the complete legacy subtree again immediately before physical removal.
# The output table pins actual adapted source bytes, not only package metadata.
COPY --from=patches /patches/del-patched /tmp/del-patched
COPY --from=patches /patches/del-patched.modules.yaml /tmp/del-patched.modules.yaml
COPY deploy/images/kibana-patches/del-inventory.cjs deploy/images/kibana-patches/del-base-inventory.json deploy/images/kibana-patches/del-output-hashes.json deploy/images/kibana-patches/install-del-migration.cjs /tmp/del-migration/
RUN /usr/share/kibana/node/default/bin/node --max-old-space-size=256 /tmp/del-migration/install-del-migration.cjs /usr/share/kibana /tmp/del-patched \
    && rm -rf /tmp/del-patched /tmp/del-patched.modules.yaml /tmp/del-migration
COPY --from=minimatch-migration /patches/mm11-prepared /tmp/mm11-prepared
COPY deploy/images/kibana-patches/mm11-migration.cjs deploy/images/kibana-patches/mm11-inputs.json deploy/images/kibana-patches/mm11-official-files.json deploy/images/kibana-patches/mm11-output-files.json deploy/images/kibana-patches/install-del-migration.cjs deploy/images/kibana-patches/del-inventory.cjs deploy/images/kibana-patches/del-base-inventory.json deploy/images/kibana-patches/del-output-hashes.json /tmp/mm11-migration/
RUN /usr/share/kibana/node/default/bin/node --max-old-space-size=256 /tmp/mm11-migration/mm11-migration.cjs install /usr/share/kibana /tmp/mm11-prepared \
    && rm -rf /tmp/mm11-prepared /tmp/mm11-migration
# Remove the old package directories so removed upstream files cannot survive COPY.
RUN rm -rf /usr/share/kibana/node_modules/decode-uri-component \
    /usr/share/kibana/node_modules/systeminformation \
    /usr/share/kibana/node_modules/re2js \
    /usr/share/kibana/node_modules/joi \
    /usr/share/kibana/node_modules/@hapi/content \
    /usr/share/kibana/node_modules/@hono/node-server \
    /usr/share/kibana/node_modules/glob \
    /usr/share/kibana/node_modules/rimraf
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
# del's old brace-expansion is removed with its unused Glob 7 closure above.
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
# Root Minimatch and its complete official nested closure were installed above.
RUN rm -rf /usr/share/kibana/node_modules/node-forge
# Replace actual upstream library and dist bytes; do not reapply the 1.4.0 backport.
COPY --from=patches /patches/node_modules/node-forge-patched /usr/share/kibana/node_modules/node-forge
COPY deploy/images/kibana-patches/test-node-forge-patch.js deploy/images/kibana-patches/test-node-forge-chain.js deploy/images/kibana-patches/test-follow-redirects.js deploy/images/kibana-patches/test-same-line-updates.js deploy/images/kibana-patches/test-hono-node-server.js /tmp/
COPY deploy/images/kibana-patches/test-glob-migration.js deploy/images/kibana-patches/test-del-migration.cjs /tmp/
COPY deploy/images/kibana-patches/test-mm11-installed.cjs deploy/images/kibana-patches/mm11-inputs.json deploy/images/kibana-patches/mm11-official-files.json deploy/images/kibana-patches/mm11-output-files.json deploy/images/kibana-patches/install-del-migration.cjs deploy/images/kibana-patches/del-inventory.cjs deploy/images/kibana-patches/del-base-inventory.json deploy/images/kibana-patches/del-output-hashes.json /tmp/mm11-test/
RUN /usr/share/kibana/node/default/bin/node /tmp/test-node-forge-patch.js \
    && /usr/share/kibana/node/default/bin/node /tmp/test-node-forge-chain.js \
    && /usr/share/kibana/node/default/bin/node /tmp/test-follow-redirects.js \
    && /usr/share/kibana/node/default/bin/node /tmp/test-same-line-updates.js \
    && /usr/share/kibana/node/default/bin/node /tmp/test-hono-node-server.js \
    && /usr/share/kibana/node/default/bin/node --max-old-space-size=256 /tmp/test-glob-migration.js \
    && /usr/share/kibana/node/default/bin/node --max-old-space-size=256 /tmp/mm11-test/test-mm11-installed.cjs \
    && /usr/share/kibana/node/default/bin/node --max-old-space-size=256 /tmp/test-del-migration.cjs \
    && rm /tmp/test-node-forge-patch.js /tmp/test-node-forge-chain.js /tmp/test-follow-redirects.js /tmp/test-same-line-updates.js /tmp/test-hono-node-server.js /tmp/test-glob-migration.js /tmp/test-del-migration.cjs \
    && rm -rf /tmp/mm11-test
USER 1000
