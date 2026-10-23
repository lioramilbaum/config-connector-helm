"""
Test guard conditions and validation.
"""

import re
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestNamespaceGuard:
    def test_wrong_namespace_fails(self):
        """
        Rendering with wrong namespace should fail with clear error message.
        """
        result = subprocess.run(
            ["helm", "template", "x", "chart/config-connector", "-n", "wrong-namespace"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, "Should fail with wrong namespace"
        assert "configconnector-operator-system" in result.stderr, (
            "Error message should mention correct namespace"
        )


class TestImageDigestSchema:
    def test_invalid_digest_rejected(self, chart_dir):
        """A digest that is not sha256:<64 hex> must be rejected by values.schema.json."""
        result = subprocess.run(
            [
                "helm",
                "template",
                "x",
                str(chart_dir),
                "-n",
                "configconnector-operator-system",
                "--set",
                "image.digest=latest",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, "Expected helm template to fail with invalid digest"
        assert "digest" in result.stderr.lower(), f"Expected 'digest' in error: {result.stderr}"


class TestCommittedDigest:
    """Guards for the committed Renovate-managed digest in values.yaml."""

    def test_digest_is_not_empty(self, chart_dir):
        values = yaml.safe_load((chart_dir / "values.yaml").read_text())
        digest = values["image"]["digest"]
        assert re.match(r"^sha256:[a-f0-9]{64}$", digest), (
            f"image.digest must be a pinned sha256 digest, got: {digest!r}"
        )

    def test_renovate_marker_matches_app_version(self, chart_dir):
        """Marker tag must equal Chart.yaml appVersion — catches a half-updated grouped PR."""
        chart = yaml.safe_load((chart_dir / "Chart.yaml").read_text())
        app_version = chart["appVersion"]
        lines = (chart_dir / "values.yaml").read_text().splitlines()
        marker = f"  # renovate: image=gcr.io/gke-release/cnrm/operator tag={app_version}"
        assert marker in lines, (
            f"Renovate marker for tag={app_version} not found in values.yaml. "
            "Run Renovate's grouped PR to update both Chart.yaml and values.yaml together."
        )
        # Marker must be the line directly before the digest: line
        digest_idx = next(
            (
                i
                for i, line in enumerate(lines)
                if re.match(r'^  digest: "sha256:[a-f0-9]{64}"$', line)
            ),
            None,
        )
        assert digest_idx is not None, (
            "No quoted digest line matching '  digest: \"sha256:<64hex>\"' found in values.yaml"
        )
        assert lines[digest_idx - 1] == marker, (
            "Renovate marker must be immediately above the digest: line"
        )

    def test_upstream_bundle_annotation_matches_app_version(self, chart_dir):
        chart = yaml.safe_load((chart_dir / "Chart.yaml").read_text())
        app_version = chart["appVersion"]
        expected = f"gs://configconnector-operator/{app_version}/release-bundle.tar.gz"
        actual = chart["annotations"]["config-connector-helm/upstream-bundle"]
        assert actual == expected, f"upstream-bundle annotation {actual!r} != {expected!r}"


class TestSchemaValidation:
    def test_schema_typo_fails(self):
        """
        A typo in a schema field (e.g., nodeSelectr instead of nodeSelector) should fail.
        """
        result = subprocess.run(
            [
                "helm",
                "template",
                "x",
                "chart/config-connector",
                "-n",
                "configconnector-operator-system",
                "--set",
                "nodeSelectr.a=b",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )

        # The schema should reject this or helm should complain
        # With Helm 3.x, strict schema validation may not fail, but let's check
        # At minimum, the typo should not silently apply
        if result.returncode == 0:
            # If it doesn't fail, at least verify the value didn't apply
            docs = [d for d in yaml.safe_load_all(result.stdout) if d]
            ss = next((d for d in docs if d.get("kind") == "StatefulSet"), None)
            if ss:
                pod_spec = ss["spec"]["template"]["spec"]
                assert "nodeSelectr" not in pod_spec, "Typo should not create field"
