# AGENTS.md: config-connector-helm

Guidance for AI coding agents working in this repository.

## What this repo is

A Helm chart for the Google Config Connector (KCC) operator. There is no upstream Helm chart; the operator ships only as a tar.gz release bundle containing manifests. This repository packages those manifests as a Helm chart published to GHCR as an OCI image.

## Repository layout

```
chart/config-connector/
  Chart.yaml                       # Chart metadata; version == KCC version
  values.yaml                      # All override defaults (reproduces upstream exactly)
  values.schema.json               # Strict JSON Schema for validation
  templates/
    _helpers.tpl                   # Label and image rendering helpers
    operator.yaml                  # Core template: splits, parses, applies overrides
    NOTES.txt                      # Post-install instructions
  files/
    .gitignore                     # Prevents committing the manifest (MUST NOT be committed)
  .helmignore                      # Standard Helm package ignores
scripts/
  fetch-manifest.sh                # Download KCC bundle from GCS, extract manifest
  discover_versions.py             # Discover publishable KCC versions
tests/
  conftest.py                      # pytest fixtures for rendering and loading
  test_render.py                   # Rendering correctness (default, overrides)
  test_guards.py                   # Validation and guard conditions
  test_package.py                  # Packaging validation
  test_discover.py                 # Version discovery logic (pure functions)
  e2e/flux/
    ocirepository.yaml             # Test OCIRepository for Flux e2e
    helmrelease.yaml               # Test HelmRelease for Flux e2e
.github/workflows/
  ci.yaml                          # Pull request linting and testing
  test.yaml                        # Reusable test workflow (unit, e2e-helm, e2e-flux)
  publish.yaml                     # Scheduled discovery, test, package, sign, publish
mise.toml                          # Pinned tool versions and task definitions
pyproject.toml                     # Python project metadata (pytest, pyyaml)
renovate.json5                     # Renovate config: KCC version + operator digest in one "Config Connector" PR; all other deps in one "Dev tools" PR
README.md                          # User-facing documentation
LICENSE                            # Apache 2.0 (created by GitHub)
NOTICE                             # Attribution to upstream
AGENTS.md                          # This file
```

## Key invariants

### The tested-baseline pin

Chart version and appVersion are pinned to 1.158.0 in Chart.yaml. This is the last-tested baseline and is bumped by Renovate when a new KCC release becomes available. Until tested in CI and merged, the repo points to this baseline.

### Never commit files/configconnector-operator.yaml

The manifest is downloaded at package time by scripts/fetch-manifest.sh and is excluded by chart/config-connector/files/.gitignore. It MUST NOT be committed. Reason: the file is 3500 lines and changes per release; storing it in Git defeats the purpose of declarative packaging. Renovate bumps Chart.yaml; the CI fetch-manifest job downloads the actual bundle.

### Namespace is hard-coded

The operator binary hard-codes the namespace to configconnector-operator-system and cannot be changed. The chart guards this in operator.yaml with an explicit `.Release.Namespace` check. Users MUST install into this namespace.

### Operator image digest is committed and Renovate-managed

`image.digest` in `chart/config-connector/values.yaml` is the digest of `gcr.io/gke-release/cnrm/operator:<appVersion>`. It is committed and must be a non-empty `sha256:` digest. It is preceded by a Renovate marker on the line directly above it, with exactly two-space indentation:

```yaml
  # renovate: image=gcr.io/gke-release/cnrm/operator tag=1.158.0
  digest: "sha256:..."
```

The marker tag must equal `Chart.yaml` appVersion. Renovate updates the marker tag and the digest together, in one grouped "Config Connector" PR with the `Chart.yaml` version bump. Digest-type updates are not automerged (automerge covers only minor and patch).

`tests/test_guards.py` (`TestCommittedDigest`) enforces that the digest is non-empty and the marker tag equals appVersion. `tests/test_render.py` (`TestDefaultDigestPin`) confirms the default render applies the committed digest. Do not edit the digest by hand; only Renovate should update it.

### How to fetch the manifest

```bash
scripts/fetch-manifest.sh
```

This script:
1. Downloads from `gs://configconnector-operator/<version>/release-bundle.tar.gz`
2. Verifies MD5 from GCS headers
3. Extracts only `operator-system/configconnector-operator.yaml` (not autopilot)
4. Asserts the image tag matches the version
5. Outputs the SHA256 of the fetched file

## The publish workflow

Triggers on push to `main` when `chart/config-connector/Chart.yaml` changes, and on manual dispatch.

1. **resolve-version**: Reads version from `inputs.version` (manual dispatch) or Chart.yaml; checks GHCR idempotency
2. **test**: Runs test.yaml (unit, e2e-helm, e2e-flux)
3. **publish**:
   - Fetch manifest
   - `helm package` to create .tgz
   - Push to GHCR as OCI image
   - Sign with cosign keyless
   - Verify signature
4. **verify-flux**: Pull real artifact from GHCR with Flux, verify cosign signature via OCIRepository

All action SHAs are pinned to known-good digests.

## Backfill (manual dispatch)

To publish a specific older version:

```bash
gh workflow run publish.yaml -f version=1.157.0 -f force=false
```

**Note:** this only works for the version currently pinned in `Chart.yaml` appVersion and `values.yaml`. Running with any other version causes the `test` job to fail because the committed digest marker does not match. To backfill an older version, you must first update `values.yaml` with the matching digest.

With `force=true`, even already-published versions are included.

The committed digest in `values.yaml` belongs to the current appVersion only. A backfill with a different version fails the test job because the marker tag in values.yaml differs from the version being tested.

## Testing locally

```bash
# Ensure mise is installed: https://mise.jdx.dev/
mise install

# Fetch the manifest for 1.158.0
mise run fetch

# Run all tests
mise run test

# Lint scripts and workflows
mise run lint

# Render the chart (requires namespace argument)
helm template x chart/config-connector -n configconnector-operator-system
```

## How the rendering works

operator.yaml is the core template:

1. **Guard**: Fail if `.Release.Namespace != "configconnector-operator-system"`
2. **Read**: Get the upstream manifest from files/configconnector-operator.yaml via `.Files.Get`
3. **Split**: Regex split on `(?m)^---\s*$` to get individual YAML documents
4. **Parse**: For each non-empty document:
   - Parse with `fromYaml`
   - Skip Namespace objects (we don't create the namespace)
   - Skip CRD objects if `crds.enabled=false`
   - Add Helm standard labels (via `config-connector.labels` helper)
   - Add `helm.sh/resource-policy: keep` annotation to CRDs if `crds.keep=true`
5. **StatefulSet overrides**:
   - Guard: fail if not exactly 1 StatefulSet with exactly 1 container named "manager"
   - Guard: fail if upstream image tag != Chart.AppVersion (version mismatch check)
   - Override container image if `image.tag`, `image.repository`, or `image.digest` set. When `image.digest` is set, the image renders as `repo:tag@digest`
   - Override resources if `resources` non-empty
   - Set/merge GOMEMLIMIT env var if `goMemLimit` set
   - Set pod spec scheduling (nodeSelector, tolerations, affinity, topologySpreadConstraints, priorityClassName)
   - Merge pod template metadata (annotations, labels)
6. **ServiceAccount overrides**:
   - Merge `serviceAccount.annotations` into metadata.annotations
7. **Emit**: Output each processed object separated by `---`

The template preserves the upstream manifest byte-for-byte (except for overrides), ensuring rendered output is deterministic and diffable.

## Verify your changes

Before pushing:

```bash
# Fetch the manifest
scripts/fetch-manifest.sh

# Lint the chart
helm lint chart/config-connector -n configconnector-operator-system

# Render with defaults
helm template x chart/config-connector -n configconnector-operator-system | wc -l

# Run all tests
uv run pytest tests/ -v

# Validate each rendered object with kubeconform
helm template x chart/config-connector -n configconnector-operator-system | kubeconform -strict -kubernetes-version 1.30.0 -skip CustomResourceDefinition
```

## Publishing a new release (manual checklist)

1. Renovate opens one grouped "Config Connector" PR that bumps Chart.yaml version and appVersion and updates the operator image digest in values.yaml
2. CI runs, downloads the bundle, tests it
3. Review and merge
4. The scheduled publish workflow picks it up and publishes to GHCR

For an out-of-schedule publish, use `gh workflow run`.
