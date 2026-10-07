"""
Test packaging of the Config Connector Helm chart.
"""

import subprocess
import tarfile
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestPackaging:
    def test_package_creates_tgz(self):
        """
        helm package should create a .tgz file.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["helm", "package", "chart/config-connector", "-d", tmpdir],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"helm package failed: {result.stderr}"

            tgzs = list(Path(tmpdir).glob("*.tgz"))
            assert len(tgzs) == 1, f"Expected 1 .tgz file, got {len(tgzs)}"

    def test_package_version_matches(self):
        """
        Packaged chart version should match Chart.yaml version.
        """
        chart_yaml_path = REPO_ROOT / "chart/config-connector/Chart.yaml"
        with open(chart_yaml_path) as f:
            chart = yaml.safe_load(f)

        version = chart["version"]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["helm", "package", "chart/config-connector", "-d", tmpdir],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0

            tgz_files = list(Path(tmpdir).glob("config-connector-*.tgz"))
            assert len(tgz_files) == 1

            tgz_name = tgz_files[0].name
            assert version in tgz_name, f"Version {version} not in filename {tgz_name}"

    def test_package_contains_manifest(self):
        """
        If manifest exists, packaged chart should contain it in the package.
        """
        manifest_path = REPO_ROOT / "chart/config-connector/files/configconnector-operator.yaml"

        if not manifest_path.exists():
            pytest.skip("Upstream manifest not fetched")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["helm", "package", "chart/config-connector", "-d", tmpdir],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0

            tgz_files = list(Path(tmpdir).glob("config-connector-*.tgz"))
            assert len(tgz_files) == 1

            with tarfile.open(tgz_files[0]) as tar:
                names = tar.getnames()
                assert any("configconnector-operator.yaml" in n for n in names), (
                    "Manifest not found in package"
                )

    def test_package_no_autopilot(self):
        """
        Packaged chart should not contain any autopilot-related files.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["helm", "package", "chart/config-connector", "-d", tmpdir],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0

            tgz_files = list(Path(tmpdir).glob("config-connector-*.tgz"))
            assert len(tgz_files) == 1

            with tarfile.open(tgz_files[0]) as tar:
                names = tar.getnames()
                autopilot_files = [n for n in names if "autopilot" in n]
                assert len(autopilot_files) == 0, (
                    f"Found autopilot files in package: {autopilot_files}"
                )
