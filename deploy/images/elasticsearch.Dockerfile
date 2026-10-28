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
USER 1000
