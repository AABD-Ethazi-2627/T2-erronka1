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
