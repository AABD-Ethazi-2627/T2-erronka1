#!/bin/sh
# Avoid the upstream installer's get.trivy.dev redirector. Pin official bytes.
set -eu
destination=${1:?Usage: install_trivy_release.sh destination-directory}
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
    echo 'This installer pins the Linux x86_64 Trivy release only' >&2
    exit 2
fi
test ! -e "$destination/trivy"
download_dir=$(mktemp -d)
trap 'rm -rf -- "$download_dir"' EXIT HUP INT TERM
sh "$(dirname "$0")/trivy-download-curl.sh" --fail --location --silent --show-error \
    --output "$download_dir/trivy.tar.gz" \
    https://github.com/aquasecurity/trivy/releases/download/v0.76.1/trivy_0.76.1_Linux-64bit.tar.gz
printf '%s  %s\n' c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0 \
    "$download_dir/trivy.tar.gz" | sha256sum --check --status
tar -xzf "$download_dir/trivy.tar.gz" -C "$download_dir" trivy
mkdir -p "$destination"
install -m 0755 "$download_dir/trivy" "$destination/trivy"
"$destination/trivy" --version
