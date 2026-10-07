"""
Test fixtures for Config Connector Helm chart.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def helm_template(tmp_path):
    """
    Fixture that runs helm template and returns parsed YAML documents.
    Usage: docs = helm_template("-n", "configconnector-operator-system", "--set", "key=value")
    Returns a list of parsed YAML objects.
    """

    def _render(*args, namespace="configconnector-operator-system", set_values=None):
        cmd = ["helm", "template", "x", "chart/config-connector", "-n", namespace]

        if set_values:
            for key, value in set_values.items():
                cmd.extend(["--set", f"{key}={value}"])

        cmd.extend(args)

        result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"helm template failed: {result.stderr}")

        docs = [doc for doc in yaml.safe_load_all(result.stdout) if doc]
        return docs

    return _render


@pytest.fixture
def upstream_manifest():
    """
    Load the upstream manifest file if it exists.
    Returns a list of parsed YAML documents.
    Skips test if file does not exist.
    """
    manifest_path = REPO_ROOT / "chart/config-connector/files/configconnector-operator.yaml"

    if not manifest_path.exists():
        pytest.skip("Upstream manifest not fetched")

    with open(manifest_path) as f:
        docs = [doc for doc in yaml.safe_load_all(f) if doc]

    return docs


def get_object_by_kind_name(docs: List[Dict[str, Any]], kind: str, name: str) -> Dict[str, Any]:
    """
    Helper to find an object in a list by kind and name.
    """
    for doc in docs:
        if doc.get("kind") == kind and doc.get("metadata", {}).get("name") == name:
            return doc
    return None
