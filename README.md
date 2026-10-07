# Config Connector Helm Chart

A Helm chart for the Google Config Connector (KCC) operator. Ships the upstream operator manifest as-is without modification.

## Why this exists

There is no upstream Helm chart for the KCC operator (see [GoogleCloudPlatform/k8s-config-connector#6430](https://github.com/GoogleCloudPlatform/k8s-config-connector/issues/6430)). The operator ships only as `gs://configconnector-operator/<version>/release-bundle.tar.gz`. This chart downloads the bundle at package time, extracts the operator manifest, and makes it available via Helm.

## Versioning

- **Chart version** == **KCC version** (e.g., 1.158.0)
- **Immutable tags**: each version is published once and never changed
- Chart and appVersion are always identical

## Quick start

### Prerequisites

- Kubernetes 1.27+
- Helm 3.10+
- kubectl configured to access your cluster

### Installation

```bash
# Add the Helm repository
helm repo add config-connector oci://ghcr.io/lioramilbaum/config-connector-helm

# Install the chart
helm install config-connector config-connector/config-connector \
  --namespace configconnector-operator-system \
  --create-namespace \
  --wait
```

### Enabling Config Connector

After installation, create a ConfigConnector resource:

```bash
kubectl apply -f - <<'EOF'
apiVersion: cnrm.cloud.google.com/v1
kind: ConfigConnector
metadata:
  name: configconnector.cnrm.cloud.google.com
spec:
  mode: cluster
  credentialSecretName: google-cloud-key
EOF
```

This enables management of GCP resources in this cluster. For detailed instructions, see [Config Connector documentation](https://cloud.google.com/config-connector/docs).

## Flux integration

### With signature verification

```yaml
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: OCIRepository
metadata:
  name: config-connector-helm
spec:
  interval: 10m
  url: oci://ghcr.io/lioramilbaum/config-connector-helm/config-connector
  ref:
    tag: 1.158.0
  verify:
    provider: cosign
    matchOIDCIdentity:
      - issuer: https://token.actions.githubusercontent.com
        subject: https://github.com/lioramilbaum/config-connector-helm/.github/workflows/publish.yaml@refs/heads/main
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: config-connector
spec:
  chart:
    spec:
      chart: config-connector
      sourceRef:
        kind: OCIRepository
        name: config-connector-helm
  targetNamespace: configconnector-operator-system
  install:
    crds: Create
    createNamespace: true
  upgrade:
    crds: CreateReplace
```

## Values

All defaults reproduce the upstream bundle exactly. Key values:

### CRDs

| Key | Default | Description |
|-----|---------|-------------|
| `crds.enabled` | `true` | Install CustomResourceDefinition objects |
| `crds.keep` | `true` | Keep CRDs when chart is uninstalled (recommended) |

### Image

| Key | Default | Description |
|-----|---------|-------------|
| `image.repository` | `""` (uses upstream) | Container image repository override |
| `image.tag` | `""` (uses Chart.appVersion) | Container image tag override |
| `image.digest` | `""` | Container image digest (optional, for pinning) |
| `image.pullPolicy` | `""` (uses upstream Always) | Image pull policy |
| `imagePullSecrets` | `[]` | Image pull secrets for private registries |

### Resources

| Key | Default | Description |
|-----|---------|-------------|
| `resources` | `{}` | Container requests/limits (empty = use upstream 100m/512Mi request, 1Gi limit) |
| `goMemLimit` | `""` | Go runtime memory limit (empty = use upstream 900MiB) |

### Pod scheduling

| Key | Default | Description |
|-----|---------|-------------|
| `nodeSelector` | `{}` | Pod node selection constraints |
| `tolerations` | `[]` | Pod tolerations |
| `affinity` | `{}` | Pod affinity rules |
| `topologySpreadConstraints` | `[]` | Topology spread constraints |
| `priorityClassName` | `""` | Pod priority class name |

### Pod metadata

| Key | Default | Description |
|-----|---------|-------------|
| `podAnnotations` | `{}` | Additional pod annotations (not in selector) |
| `podLabels` | `{}` | Additional pod labels (not in selector) |

### Service account

| Key | Default | Description |
|-----|---------|-------------|
| `serviceAccount.annotations` | `{}` | Service account annotations |

### Common labels

| Key | Default | Description |
|-----|---------|-------------|
| `commonLabels` | `{}` | Labels applied to all resources |

## CRD handling

By default, CRDs are installed and marked with `helm.sh/resource-policy: keep`, so they remain when the chart is uninstalled. This is recommended for production to avoid accidental resource deletion.

To remove CRDs on uninstall, set `crds.keep: false`.

To disable CRD installation entirely, set `crds.enabled: false`.

## Namespace

The operator binary hard-codes the namespace to `configconnector-operator-system`. The chart enforces this and will fail to render if installed into a different namespace. See [GoogleCloudPlatform/k8s-config-connector/blob/main/experiments/composite/cnrm-module/static/constants.go](https://github.com/GoogleCloudPlatform/k8s-config-connector/blob/main/experiments/composite/cnrm-module/static/constants.go).

## Architecture

The operator only supports linux/amd64. ARM64 support is not available.

## Verification

### Helm template validation

After rendering, validate with kubeconform:

```bash
helm template x chart/config-connector -n configconnector-operator-system | \
  kubeconform -strict -kubernetes-version 1.30.0 -skip CustomResourceDefinition
```

### Signature verification

All published charts are signed with cosign using GitHub OIDC keyless signing. Verify locally:

```bash
cosign verify \
  --certificate-identity https://github.com/lioramilbaum/config-connector-helm/.github/workflows/publish.yaml@refs/heads/main \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/lioramilbaum/config-connector-helm/config-connector:1.158.0
```

## How publishing works

1. **Discovery** (every 6 hours): Query GitHub for new KCC releases, check GCS for availability
2. **Testing**: Run unit and e2e tests for each new version
3. **Publishing**: Package, sign, and push to GHCR as an OCI image
4. **Verification**: Pull and verify in a Flux e2e test

All workflows are CI-driven. Manual backfill of older versions is supported via workflow dispatch.

## Development

See [AGENTS.md](AGENTS.md) for internal documentation.

### Local testing

```bash
# Install tools
mise install

# Fetch the upstream manifest for the test version
mise run fetch

# Run tests
mise run test

# Lint
mise run lint

# Render the chart
helm template x chart/config-connector -n configconnector-operator-system
```

## License

This chart is licensed under the Apache License 2.0. The upstream Config Connector operator is copyright Google LLC and licensed under the Apache License 2.0. See [NOTICE](NOTICE).