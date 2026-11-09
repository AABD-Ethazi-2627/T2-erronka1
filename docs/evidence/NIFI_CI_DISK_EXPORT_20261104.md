# NiFi CI: disk exhaustion during nested-image export

Run **41822718551**, job **126549608040**, source `ea9e84f`, failed differently
from the earlier completed nested audits. The image build and normal Trivy scan
passed; the normal report validates with zero findings. The archive-audit image
also built successfully. Trivy then failed while Docker exported a layer:

```text
unable to export the image: Error response from daemon: write
/var/lib/docker/tmp/docker-export-2851288401/blobs/sha256/9a3f01aa8fad636c19a1848b58c8d1c6d2a193424e43242838fb6645f27c220e:
no space left on device
```

There is **no completed nested report** from this job. It does not confirm,
reduce or extend the previous 59-tuple findings. The normal scan is not a
replacement for the missing nested scan. [Exact identities and log hashes](NIFI_CI_DISK_EXPORT_20261104.json).

The workflow now reclaims disposable build cache **after** both runtime and
archive images have built, before Trivy exports the larger archive image. The
GitHub-hosted job has its own Docker daemon; `docker builder prune --all --force`
removes its unused intermediate build cache. Both tagged images are retained
and explicitly inspected afterward. Disk usage before and after reclamation
and Docker storage usage are printed for diagnosis. No image/volume prune,
runtime-input change, scanner exception or coverage reduction is introduced.

`actionlint` passes. The existing infrastructure, nested-archive and image-gate
suites pass **17 tests and 23 subtests**. No local build-cache deletion or image
rebuild was run. Reclaimed bytes and successful nested export must be established
by fresh CI; the disk-space repair is not yet runtime-verified. Even if export
succeeds, previously identified vulnerable dependencies remain blocking until
their separate remediation and final scan pass.
