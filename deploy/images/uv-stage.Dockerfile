# Shared pinned uv source build: only rustls changes relative to upstream 0.13.6.
FROM rust:1.99.1-alpine@sha256:7e9e2d068a107a2adafd19930011178d14a78326053cd4c3a9f7ad3fd049557d AS uv-build
RUN apk add --no-cache clang cmake make musl-dev perl pkgconf patch
ADD --checksum=sha256:c2e01687fbbcb109277698ec97baca46e1547656ad580abf6d993f9c459af1c7 https://github.com/astral-sh/uv/archive/refs/tags/0.13.6.tar.gz /tmp/uv.tar.gz
RUN mkdir /src && tar -xzf /tmp/uv.tar.gz -C /src --strip-components=1
COPY deploy/images/uv-rustls.patch /tmp/uv-rustls.patch
WORKDIR /src
# Preserve embedded dependency metadata so Trivy can still audit the Rust closure.
RUN patch -p1 < /tmp/uv-rustls.patch \
    && cargo install --locked --version 0.7.7 cargo-auditable \
    && CARGO_BUILD_JOBS=4 CARGO_PROFILE_RELEASE_LTO=false CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16 \
       cargo auditable build --locked --release --package uv --bin uv --bin uvx
FROM scratch AS uv
COPY --from=uv-build /src/target/release/uv /uv
COPY --from=uv-build /src/target/release/uvx /uvx
ENTRYPOINT ["/uv"]
