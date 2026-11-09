# Local serial image builds

The shared patched uv stage accepts `UV_BUILD_JOBS`, a positive decimal integer
without a leading zero. Its default is four. It sets `CARGO_BUILD_JOBS` for both
the pinned `cargo-auditable` installation and the locked uv/uvx compilation.
It does not change source versions, the Rust lock, the rustls patch, release
optimization settings, embedded audit metadata, or the final runtime.

On a constrained host, after stopping only the rehearsal's own runtime services,
build one image at a time from the repository root:

```sh
docker build --progress=plain --build-arg UV_BUILD_JOBS=1 \
  -f scoring/Dockerfile -t cnc-guard-local:api .
docker build --progress=plain --build-arg UV_BUILD_JOBS=1 \
  -f dashboard_laneki/Dockerfile -t cnc-guard-local:dashboard .
```

The same argument applies to `deploy/images/uv.Dockerfile` and
`deploy/images/nifi.Dockerfile`. Identical stage text and the same argument allow
Docker to reuse the completed uv stage across these builds. A different argument
changes the relevant build cache key. A single Cargo job limits parallel work,
not total build memory or disk; it does not alter the full-lab resource preflight.
Run the existing image scans and runtime checks after a successful build.

`deploy/images/uv-stage.Dockerfile` is canonical. The repository has no generator
for this prefix: copy it byte-for-byte to the start of the four consumers, keeping
their suffixes intact. `python -m scripts.image_inventory --check` rejects drift.
The shell guard is tested without Cargo, Docker builds, services or network in
`tests/test_uv_build_jobs.py`.

The Filebeat builder separately accepts `GO_BUILD_JOBS`, with the same positive
decimal validation and a default of two. It exports `GOMAXPROCS` for both Go
commands and passes the same value to `go build -p` to bound concurrent package
compilation. The Beats archive, Go image, module version changes, CGO setting,
trimpath option, binary output path and final runtime stage are unchanged.

```sh
docker build --progress=plain --build-arg GO_BUILD_JOBS=1 \
  -f deploy/images/filebeat.Dockerfile -t cnc-guard-audit:filebeat .
```

This build control alone is not evidence of image acceptance. The later
[local image report](../evidence/LOCAL_CONTAINERS_20261103.md) records an actual
serial build, scan, binary reachability check and Kafka producer rehearsal.
The existing `filebeat-os` target isolates OS updates
only and removes the old binary; it is not a final runnable Filebeat image.
One Go job does not bound total memory, module-cache size or disk usage. Preserve
the resource preflight, image scan gate and binary reachability check, then test
configuration/startup and actual Kafka publishing from the resulting image.
`tests/test_filebeat_build_jobs.py` executes the actual RUN guard with harmless
Go/tar stubs, without compiling, contacting services or using the network.
