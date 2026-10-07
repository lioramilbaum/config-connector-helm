#!/usr/bin/env python3
"""
Discover available KCC versions to publish to the Helm repository.

Pure functions:
- parse_releases(data): filter and extract versions from GitHub releases JSON
- parse_existing_tags(crane_output): extract versions from crane ls output
- select_versions(releases, existing, min_version, max_per_run): select candidates

Main entry: queries GitHub releases, checks GCS for availability, outputs JSON.
"""

import json
import re
import subprocess
import sys
from typing import List


def _ver(v: str) -> tuple:
    """
    Convert version string to tuple of integers for proper semantic comparison.
    Examples: "1.9.0" -> (1, 9, 0), "1.10.0" -> (1, 10, 0)
    """
    return tuple(int(x) for x in v.split("."))


def parse_releases(data: dict) -> List[str]:
    r"""
    Filter GitHub releases: exclude drafts, pre-releases.
    Extract versions matching ^v(\d+\.\d+\.\d+)$, strip 'v' prefix.
    Return ascending sorted list (by semantic version, not string).
    """
    versions = []
    for item in data.get("data", []):
        if item.get("draft") or item.get("prerelease"):
            continue
        tag = item.get("tag_name", "")
        match = re.match(r"^v(\d+\.\d+\.\d+)$", tag)
        if match:
            versions.append(match.group(1))
    return sorted(versions, key=_ver)


def parse_existing_tags(crane_output: str) -> List[str]:
    """
    Parse crane ls output (one tag per line).
    Return list of versions (tags are versions in this repo).
    Empty list if output contains NAME_UNKNOWN or is empty.
    Sorted by semantic version, not string.
    """
    if "NAME_UNKNOWN" in crane_output or not crane_output.strip():
        return []
    tags = [line.strip() for line in crane_output.strip().split("\n") if line.strip()]
    return sorted(tags, key=_ver)


def select_versions(
    releases: List[str],
    existing: List[str],
    min_version: str = "0.0.0",
    max_per_run: int = 5,
    force: bool = False,
) -> List[str]:
    """
    Select versions >= min_version that are not in existing (unless force=True).
    Return list of up to max_per_run versions in ascending order.
    """
    if force:
        candidates = [v for v in releases if _ver(v) >= _ver(min_version)]
    else:
        candidates = [v for v in releases if _ver(v) >= _ver(min_version) and v not in existing]
    return sorted(candidates, key=_ver)[:max_per_run]


def check_gcs_availability(version: str) -> bool:
    """
    Check if the release bundle exists on GCS with HEAD request.
    Return True if 200/302, False otherwise.
    Exit 3 is handled by the caller's workflow.
    """
    url = f"https://storage.googleapis.com/configconnector-operator/{version}/release-bundle.tar.gz"
    try:
        result = subprocess.run(
            ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True,
            text=True,
            timeout=10,
        )
        code = result.stdout.strip()
        return code in ("200", "302")
    except Exception:
        return False


def main():
    """
    Discover available versions and output matrix JSON.
    Supports:
    - --version X [--force]: backfill specific version
    - --min-version X: start from version X (default: 0.0.0)
    - --max-per-run N: limit to N versions per run (default: 5)
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="Backfill specific version")
    parser.add_argument("--force", action="store_true", help="Include existing versions")
    parser.add_argument("--min-version", default="0.0.0")
    parser.add_argument("--max-per-run", type=int, default=5)
    args = parser.parse_args()

    if args.version:
        # Backfill mode: check single version
        if not check_gcs_availability(args.version):
            print(json.dumps({"include": []}))
            sys.exit(0)

        # Check if version already exists in GHCR (unless --force)
        if not args.force:
            try:
                result = subprocess.run(
                    ["crane", "ls", "ghcr.io/lioramilbaum/config-connector-helm/config-connector"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                existing = parse_existing_tags(result.stdout)
                if args.version in existing:
                    print(json.dumps({"include": []}))
                    sys.exit(0)
            except Exception:
                pass

        print(json.dumps({"include": [{"version": args.version}]}))
        sys.exit(0)

    # Discover mode: query GitHub releases
    try:
        result = subprocess.run(
            ["gh", "api", "--paginate", "repos/GoogleCloudPlatform/k8s-config-connector/releases"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(json.dumps({"include": []}))
            sys.exit(0)
        releases = parse_releases(json.loads(result.stdout))
    except Exception:
        print(json.dumps({"include": []}))
        sys.exit(0)

    # Get existing tags
    try:
        result = subprocess.run(
            ["crane", "ls", "ghcr.io/lioramilbaum/config-connector-helm/config-connector"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        existing = parse_existing_tags(result.stdout)
    except Exception:
        existing = []

    # Select versions
    candidates = select_versions(releases, existing, args.min_version, args.max_per_run, args.force)

    # Check GCS availability
    available = [v for v in candidates if check_gcs_availability(v)]

    # Output matrix
    matrix = {"include": [{"version": v} for v in available]}
    print(json.dumps(matrix))


if __name__ == "__main__":
    main()
