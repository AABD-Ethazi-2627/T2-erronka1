FROM maven:3.9.11-eclipse-temurin-25-alpine@sha256:8e5fbd12216e289fe87356e3f534f17188f6fa9bd08ffe29e745fb6bd29e9ae3 AS parquet-patch
WORKDIR /src
COPY deploy/images/elasticsearch-patches/pom.xml ./pom.xml
RUN mvn --batch-mode --no-transfer-progress package

FROM maven:3.9.11-eclipse-temurin-25-alpine@sha256:8e5fbd12216e289fe87356e3f534f17188f6fa9bd08ffe29e745fb6bd29e9ae3 AS guava-patch
WORKDIR /src
COPY deploy/images/elasticsearch-patches/guava-pom.xml ./pom.xml
RUN mvn --batch-mode --no-transfer-progress package

FROM docker.elastic.co/elasticsearch/elasticsearch-wolfi:9.5.5@sha256:c2cce72acf8dc0510c04fd5926123f630859019082edf9827daef82b6a46c9c1

USER root
RUN printf '%s\n' 'https://packages.wolfi.dev/os' > /etc/apk/repositories \
    && sed -i -E '/^(ca-certificates-bundle|glibc-2[.]44|glibc-2[.]44-locale-posix|ld-linux-2[.]44|libbrotlicommon1|libbrotlidec1|libbrotlienc1|libcrypt1-2[.]44|openssl-4[.]0-libcrypto|openssl-4[.]0-libssl)=/s/=.*$//' /etc/apk/world \
    && apk upgrade --no-cache \
    && rm -f /usr/share/elasticsearch/lib/lz4-java-1.11.1.jar \
        /usr/share/elasticsearch/modules/x-pack-ent-search/commons-lang3-3.9.jar \
        /usr/share/elasticsearch/modules/ingest-attachment/jsoup-1.21.2.jar \
        /usr/share/elasticsearch/bin/elasticsearch-sql-cli-9.5.5.jar \
        /usr/share/elasticsearch/modules/apm/elastic-apm-agent-java8-1.55.6.jar
ADD --checksum=sha256:58c8e0b813960d2a248e050c353baea73139b48a2ffc55382d42c69707e17325 \
    https://repo1.maven.org/maven2/at/yawk/lz4/lz4-java/1.11.4/lz4-java-1.11.4.jar \
    /usr/share/elasticsearch/lib/lz4-java-1.11.4.jar
ADD --checksum=sha256:4eeeae8d20c078abb64b015ec158add383ac581571cddc45c68f0c9ae0230720 \
    https://repo1.maven.org/maven2/org/apache/commons/commons-lang3/3.18.0/commons-lang3-3.18.0.jar \
    /usr/share/elasticsearch/modules/x-pack-ent-search/commons-lang3-3.18.0.jar
ADD --checksum=sha256:e9d8c856856680427f096d156f02a414289985c930998fcb519ce5be39b42003 \
    https://repo1.maven.org/maven2/org/jsoup/jsoup/1.23.2/jsoup-1.23.2.jar \
    /usr/share/elasticsearch/modules/ingest-attachment/jsoup-1.23.2.jar
ADD --checksum=sha256:bf6c3b903568bc5e0c8dbb40318ea826aec7d5eb665bb96deff05e58b2099838 \
    https://repo1.maven.org/maven2/co/elastic/apm/elastic-apm-agent-java8/1.57.1/elastic-apm-agent-java8-1.57.1.jar \
    /usr/share/elasticsearch/modules/apm/elastic-apm-agent-java8-1.57.1.jar
COPY --from=parquet-patch /src/target/parquet-jackson-patch-1.0.0.jar /tmp/parquet-jackson-patch.jar
RUN for bundle in \
        /usr/share/elasticsearch/modules/esql-datasource-iceberg/parquet-hadoop-bundle-1.18.1.jar \
        /usr/share/elasticsearch/modules/esql-datasource-parquet/parquet-hadoop-bundle-1.18.1.jar; do \
      zip -dq "$bundle" 'shaded/parquet/com/fasterxml/*' 'META-INF/maven/com.fasterxml.jackson.core/*'; \
      rm -rf /tmp/parquet-jackson-patch && mkdir /tmp/parquet-jackson-patch; \
      unzip -q /tmp/parquet-jackson-patch.jar -d /tmp/parquet-jackson-patch; \
      cd /tmp/parquet-jackson-patch; \
      zip -qr "$bundle" shaded/parquet/com/fasterxml META-INF/maven/com.fasterxml.jackson.core; \
    done \
    && rm -rf /tmp/parquet-jackson-patch /tmp/parquet-jackson-patch.jar
RUN chown 1000:0 \
        /usr/share/elasticsearch/lib/lz4-java-1.11.4.jar \
        /usr/share/elasticsearch/modules/x-pack-ent-search/commons-lang3-3.18.0.jar \
        /usr/share/elasticsearch/modules/ingest-attachment/jsoup-1.23.2.jar \
        /usr/share/elasticsearch/modules/apm/elastic-apm-agent-java8-1.57.1.jar \
    && chmod 0644 \
        /usr/share/elasticsearch/lib/lz4-java-1.11.4.jar \
        /usr/share/elasticsearch/modules/x-pack-ent-search/commons-lang3-3.18.0.jar \
        /usr/share/elasticsearch/modules/ingest-attachment/jsoup-1.23.2.jar \
        /usr/share/elasticsearch/modules/apm/elastic-apm-agent-java8-1.57.1.jar
USER 1000

USER root
ADD --checksum=sha256:b530942257fb935f8b2cfaa5f8eb5bd59c555fd8e8d01b8ce98912e077ea606c https://repo1.maven.org/maven2/com/google/guava/guava/33.7.2-jre/guava-33.7.2-jre.jar /tmp/guava-fixed.jar
ADD --checksum=sha256:35228628442e4b9797681c7cbd3b26594f6da3379159dbd0cb07094ed3aece0d https://repo1.maven.org/maven2/org/xerial/snappy/snappy-java/1.1.10.9/snappy-java-1.1.10.9.jar /usr/share/elasticsearch/modules/esql-datasource-compression-libs/snappy-java-1.1.10.9.jar
COPY --from=guava-patch /src/target/iceberg-guava-patch-1.0.0.jar /tmp/iceberg-guava-patch.jar
RUN for old in $(find /usr/share/elasticsearch -name 'guava-*-jre.jar'); do \
      target="$(dirname "$old")/guava-33.7.2-jre.jar"; rm "$old"; cp /tmp/guava-fixed.jar "$target"; chown 1000:0 "$target"; chmod 0644 "$target"; \
    done \
    && rm /usr/share/elasticsearch/modules/esql-datasource-compression-libs/snappy-java-1.1.10.8.jar \
    && zip -dq /usr/share/elasticsearch/modules/esql-datasource-iceberg/iceberg-bundled-guava-1.10.2.jar 'org/apache/iceberg/relocated/com/google/*' 'META-INF/maven/com.google.guava/*' \
    && mkdir /tmp/iceberg-guava-patch && cd /tmp/iceberg-guava-patch \
    && unzip -q /tmp/iceberg-guava-patch.jar \
    && zip -qr /usr/share/elasticsearch/modules/esql-datasource-iceberg/iceberg-bundled-guava-1.10.2.jar org/apache/iceberg/relocated/com/google META-INF/maven \
    && chown 1000:0 /usr/share/elasticsearch/modules/esql-datasource-compression-libs/snappy-java-1.1.10.9.jar \
    && chmod 0644 /usr/share/elasticsearch/modules/esql-datasource-compression-libs/snappy-java-1.1.10.9.jar \
    && rm -rf /tmp/guava-fixed.jar /tmp/iceberg-guava-patch.jar /tmp/iceberg-guava-patch
# Preserve the existing automatic-module identity and its narrow entitlement policy.
RUN mkdir -p /tmp/snappy-module/META-INF \
    && unzip -p /usr/share/elasticsearch/modules/esql-datasource-compression-libs/snappy-java-1.1.10.9.jar META-INF/MANIFEST.MF \
       | sed 's/^Automatic-Module-Name: org.xerial.snappy/Automatic-Module-Name: snappy.java/' > /tmp/snappy-module/META-INF/MANIFEST.MF \
    && cd /tmp/snappy-module \
    && zip -q /usr/share/elasticsearch/modules/esql-datasource-compression-libs/snappy-java-1.1.10.9.jar META-INF/MANIFEST.MF \
    && rm -rf /tmp/snappy-module
# GHSA-ccrj-gw8r-854m: replace real API bytes in all three isolated modules.
# Keep API/context/common aligned. The six SDKs are aligned below; retain the
# aligned exporters below and vendor instrumentation.
ADD --checksum=sha256:538d1dff2f9a37aecbc0ef98fd17273a3affb058e734e6763a3a07a38a5fdc59 https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-api/1.67.0/opentelemetry-api-1.67.0.jar /tmp/opentelemetry-api-1.67.0.jar
ADD --checksum=sha256:40fb813fb5e27ec2691daa29c81b572b5b1541ef9b41e62490c3ee3e6407c55e https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-context/1.67.0/opentelemetry-context-1.67.0.jar /tmp/opentelemetry-context-1.67.0.jar
ADD --checksum=sha256:da97bdb395418e16ecdcbe7ad3497f45b9e767ceda4ae7e86133e7a757ac377f https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-common/1.67.0/opentelemetry-common-1.67.0.jar /tmp/opentelemetry-common-1.67.0.jar
RUN for module in apm esql-datasource-gcs repository-gcs; do \
      for artifact in api context common; do \
        target="/usr/share/elasticsearch/modules/$module"; \
        test -f "$target/opentelemetry-$artifact-1.62.0.jar"; \
        rm "$target/opentelemetry-$artifact-1.62.0.jar"; \
        cp "/tmp/opentelemetry-$artifact-1.67.0.jar" "$target/"; \
        chown 1000:0 "$target/opentelemetry-$artifact-1.67.0.jar"; \
        chmod 0644 "$target/opentelemetry-$artifact-1.67.0.jar"; \
      done; \
    done \
    && rm /tmp/opentelemetry-*-1.67.0.jar
# SDK 1.62 uses API-internal ConfigUtil removed by API 1.67. Align the six SDK
# artifacts; EsLoaderProbe exercises configuration, signals and exporter builders.
ADD --checksum=sha256:52a8f599a368a3d62185e37053f6a53175d6fbe3ecc1d565baba13b1a854267f https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-sdk/1.67.0/opentelemetry-sdk-1.67.0.jar /tmp/sdk/opentelemetry-sdk-1.67.0.jar
ADD --checksum=sha256:628a4c00db9561ff4c608a650d5e7fd66a1e153ccdf1ba3cdc5ac0b7c6518fea https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-sdk-common/1.67.0/opentelemetry-sdk-common-1.67.0.jar /tmp/sdk/opentelemetry-sdk-common-1.67.0.jar
ADD --checksum=sha256:14d9615c8a5dcf471dcbb74902b771dcfa8656b755ac38dce904042289ccd198 https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-sdk-trace/1.67.0/opentelemetry-sdk-trace-1.67.0.jar /tmp/sdk/opentelemetry-sdk-trace-1.67.0.jar
ADD --checksum=sha256:c157ff10da59a87a57e5236d9f3290792d9b749433be5e5b449a7d1604c320a9 https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-sdk-metrics/1.67.0/opentelemetry-sdk-metrics-1.67.0.jar /tmp/sdk/opentelemetry-sdk-metrics-1.67.0.jar
ADD --checksum=sha256:dd0f0b625e08787af49d7e270abc6def4c2eabc2f18f5f145b7924024a3311e3 https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-sdk-logs/1.67.0/opentelemetry-sdk-logs-1.67.0.jar /tmp/sdk/opentelemetry-sdk-logs-1.67.0.jar
ADD --checksum=sha256:41eb19f6caf2c655ac3139d331f5c34283f2efdb0f0b0e58765a6cc9e27f66bc https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-sdk-extension-autoconfigure-spi/1.67.0/opentelemetry-sdk-extension-autoconfigure-spi-1.67.0.jar /tmp/sdk/opentelemetry-sdk-extension-autoconfigure-spi-1.67.0.jar
RUN for artifact in sdk sdk-common sdk-trace sdk-metrics sdk-logs sdk-extension-autoconfigure-spi; do \
      target=/usr/share/elasticsearch/modules/apm; \
      test -f "$target/opentelemetry-$artifact-1.62.0.jar"; \
      rm "$target/opentelemetry-$artifact-1.62.0.jar"; \
      cp "/tmp/sdk/opentelemetry-$artifact-1.67.0.jar" "$target/"; \
      chown 1000:0 "$target/opentelemetry-$artifact-1.67.0.jar"; \
      chmod 0644 "$target/opentelemetry-$artifact-1.67.0.jar"; \
    done && rm -r /tmp/sdk
# Align exporter internal ABI with SDK 1.67; retain isolated APM realm/policy.
ADD --checksum=sha256:eb61aab6d20bf105102dfa061b478b659cec17e82a50969898046456768ba09b https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-exporter-common/1.67.0/opentelemetry-exporter-common-1.67.0.jar /tmp/exporters/opentelemetry-exporter-common-1.67.0.jar
ADD --checksum=sha256:6724a9c8f9f42de757682c6194c48d9fee4670cd19a85c37954eba526c58b836 https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-exporter-otlp/1.67.0/opentelemetry-exporter-otlp-1.67.0.jar /tmp/exporters/opentelemetry-exporter-otlp-1.67.0.jar
ADD --checksum=sha256:75530ab4d93e6fdef478d3e112713337625e70a63df357e6e7b9060c13788015 https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-exporter-otlp-common/1.67.0/opentelemetry-exporter-otlp-common-1.67.0.jar /tmp/exporters/opentelemetry-exporter-otlp-common-1.67.0.jar
ADD --checksum=sha256:0ccb54e5e1db24680b0b7b818299552477dcc7114de7ca0f7b054e6e20958b83 https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-exporter-sender-okhttp/1.67.0/opentelemetry-exporter-sender-okhttp-1.67.0.jar /tmp/exporters/opentelemetry-exporter-sender-okhttp-1.67.0.jar
ADD --checksum=sha256:234194a04aac54858df0a750d243af7b2e39df5e4eb86e9912043ad33a9f9a52 https://repo.maven.apache.org/maven2/com/squareup/okhttp3/okhttp-jvm/5.5.0/okhttp-jvm-5.5.0.jar /tmp/exporters/okhttp-jvm-5.5.0.jar
ADD --checksum=sha256:b97b640557a650d15411f2be29aef558c4e422a83653cb18ba494311dbed18be https://repo.maven.apache.org/maven2/com/squareup/okio/okio-jvm/3.18.1/okio-jvm-3.18.1.jar /tmp/exporters/okio-jvm-3.18.1.jar
RUN rm /usr/share/elasticsearch/modules/apm/opentelemetry-exporter-*-1.62.0.jar /usr/share/elasticsearch/modules/apm/okhttp-jvm-5.3.2.jar /usr/share/elasticsearch/modules/apm/okio-jvm-3.17.0.jar \
    && cp /tmp/exporters/*.jar /usr/share/elasticsearch/modules/apm/ \
    && chown 1000:0 /usr/share/elasticsearch/modules/apm/*.jar \
    && chmod 0644 /usr/share/elasticsearch/modules/apm/*.jar \
    && rm -r /tmp/exporters
ADD --checksum=sha256:fea3d78726e49620168c3f6194ff491edfd1ec89b2df06fd5d5b73e55d74a342 https://repo.maven.apache.org/maven2/io/opentelemetry/opentelemetry-api-incubator/1.67.0-alpha/opentelemetry-api-incubator-1.67.0-alpha.jar /tmp/incubator.jar
RUN rm /usr/share/elasticsearch/modules/apm/opentelemetry-api-incubator-1.60.1-alpha.jar \
    && cp /tmp/incubator.jar /usr/share/elasticsearch/modules/apm/opentelemetry-api-incubator-1.67.0-alpha.jar \
    && chown 1000:0 /usr/share/elasticsearch/modules/apm/opentelemetry-api-incubator-1.67.0-alpha.jar \
    && chmod 0644 /usr/share/elasticsearch/modules/apm/opentelemetry-api-incubator-1.67.0-alpha.jar \
    && rm /tmp/incubator.jar
# Official v9.5.5 source, with a null guard at the eight nullable span lookups.
# Preserve the named APM module and entitlement policy. No API diagnostic is
# suppressed: absent spans are handled before calling the non-null OTel API.
COPY deploy/images/elasticsearch-patches/otel-qualification/closeout-20261108/APMTracer.java /tmp/apm-source/APMTracer.java
RUN echo '5bd12c7a170309f026bb9bc2728c2294fcfcb59595926bb2fe8c0176392a841a  /tmp/apm-source/APMTracer.java' | sha256sum -c - \
    && sed -i \
      -e 's/final var span = Span.fromContextOrNull(spans.remove(spanId));/final var context = spans.remove(spanId); final var span = context == null ? null : Span.fromContextOrNull(context);/' \
      -e 's/final var span = Span.fromContextOrNull(spans.get(traceable.getSpanId()));/final var context = spans.get(traceable.getSpanId()); final var span = context == null ? null : Span.fromContextOrNull(context);/g' \
      /tmp/apm-source/APMTracer.java \
    && test "$(grep -c 'context == null ? null' /tmp/apm-source/APMTracer.java)" = 8 \
    && /usr/share/elasticsearch/jdk/bin/javac -J-Xmx256m \
       --module-path /usr/share/elasticsearch/lib:/usr/share/elasticsearch/modules/apm \
       --patch-module org.elasticsearch.telemetry.apm=/tmp/apm-source \
       -d /tmp/apm-classes /tmp/apm-source/APMTracer.java \
    && /usr/share/elasticsearch/jdk/bin/jar uf /usr/share/elasticsearch/modules/apm/apm-9.5.5.jar \
       -C /tmp/apm-classes org/elasticsearch/telemetry/apm/internal/tracing \
    && rm -r /tmp/apm-source /tmp/apm-classes
USER 1000
