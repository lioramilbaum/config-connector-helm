#!/usr/bin/env bash
set -euo pipefail

# Usage: fetch-manifest.sh <version> [dest-dir]
# Downloads the KCC operator bundle from GCS, verifies MD5, extracts only
# operator-system/configconnector-operator.yaml (not autopilot), asserts the
# operator image tag matches the requested version, copies to dest-dir
# (default: chart/config-connector/files/).
# Exits 3 if the GCS bundle returns 404 (version not yet available).

VERSION="${1:?version required}"
DEST="${2:-$(dirname "$0")/../chart/config-connector/files}"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

URL="https://storage.googleapis.com/configconnector-operator/${VERSION}/release-bundle.tar.gz"

# Download and check HTTP status
HTTP_CODE=$(curl -sS -w "%{http_code}" -o "$TMPDIR/bundle.tar.gz" \
  -H "Accept: application/octet-stream" "$URL")

if [[ "$HTTP_CODE" == "404" ]]; then
  echo "Version ${VERSION} not found on GCS" >&2
  exit 3
fi

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "HTTP $HTTP_CODE for $URL" >&2
  exit 1
fi

# Verify MD5 from GCS header
HEADER_MD5=$(curl -sI "$URL" | grep -i 'x-goog-hash:.*md5=' | sed 's/.*md5=//;s/\r//')
FILE_MD5=$(openssl dgst -md5 -binary "$TMPDIR/bundle.tar.gz" | base64)

if [[ "$HEADER_MD5" != "$FILE_MD5" ]]; then
  echo "MD5 mismatch for bundle" >&2
  exit 1
fi

# Extract only the standard operator manifest (not autopilot, not samples)
if ! tar -xzf "$TMPDIR/bundle.tar.gz" -C "$TMPDIR" \
  --wildcards --no-anchored "operator-system/configconnector-operator.yaml" 2>/dev/null; then
  # Fallback without wildcards if the above fails
  tar -xzf "$TMPDIR/bundle.tar.gz" -C "$TMPDIR" \
    "operator-system/configconnector-operator.yaml"
fi

MANIFEST="$TMPDIR/operator-system/configconnector-operator.yaml"

if [[ ! -f "$MANIFEST" ]]; then
  echo "Could not extract operator manifest from bundle" >&2
  exit 1
fi

# Assert image tag matches version
if ! grep -q "image: gcr.io/gke-release/cnrm/operator:${VERSION}" "$MANIFEST"; then
  echo "Image tag mismatch in manifest for version ${VERSION}" >&2
  exit 1
fi

mkdir -p "$DEST"
cp "$MANIFEST" "$DEST/configconnector-operator.yaml"

SHA256=$(sha256sum "$DEST/configconnector-operator.yaml" | awk '{print $1}')
echo "Fetched configconnector-operator.yaml sha256=${SHA256}"
