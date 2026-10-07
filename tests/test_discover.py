"""
Test version discovery functions from discover_versions.py
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Load the discover_versions module
discover_path = REPO_ROOT / "scripts/discover_versions.py"
spec = importlib.util.spec_from_file_location("discover_versions", discover_path)
discover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discover)


class TestParseReleases:
    def test_filters_drafts(self):
        """Draft releases should be excluded."""
        data = {
            "data": [
                {"tag_name": "v1.0.0", "draft": True},
                {"tag_name": "v1.1.0", "draft": False},
            ]
        }
        result = discover.parse_releases(data)
        assert result == ["1.1.0"]

    def test_filters_prereleases(self):
        """Pre-release versions should be excluded."""
        data = {
            "data": [
                {"tag_name": "v1.0.0-beta", "draft": False, "prerelease": True},
                {"tag_name": "v1.1.0", "draft": False, "prerelease": False},
            ]
        }
        result = discover.parse_releases(data)
        assert result == ["1.1.0"]

    def test_filters_invalid_tags(self):
        """Invalid tag formats should be excluded."""
        data = {
            "data": [
                {"tag_name": "v1.0", "draft": False},  # Missing patch
                {"tag_name": "1.0.0", "draft": False},  # No v prefix
                {"tag_name": "v1.0.0", "draft": False},  # Valid
            ]
        }
        result = discover.parse_releases(data)
        assert result == ["1.0.0"]

    def test_strips_v_prefix(self):
        """v prefix should be stripped from versions."""
        data = {
            "data": [
                {"tag_name": "v1.158.0", "draft": False},
            ]
        }
        result = discover.parse_releases(data)
        assert result == ["1.158.0"]

    def test_output_ascending(self):
        """Results should be sorted ascending."""
        data = {
            "data": [
                {"tag_name": "v1.2.0", "draft": False},
                {"tag_name": "v1.0.0", "draft": False},
                {"tag_name": "v1.1.0", "draft": False},
            ]
        }
        result = discover.parse_releases(data)
        assert result == ["1.0.0", "1.1.0", "1.2.0"]


class TestParseExistingTags:
    def test_parses_crane_output(self):
        """Parse one tag per line from crane ls output."""
        output = "1.155.0\n1.156.0\n1.157.0"
        result = discover.parse_existing_tags(output)
        assert result == ["1.155.0", "1.156.0", "1.157.0"]

    def test_handles_name_unknown(self):
        """NAME_UNKNOWN indicates repo doesn't exist yet."""
        output = "NAME_UNKNOWN"
        result = discover.parse_existing_tags(output)
        assert result == []

    def test_handles_empty_output(self):
        """Empty output indicates no tags."""
        output = ""
        result = discover.parse_existing_tags(output)
        assert result == []

    def test_output_sorted(self):
        """Results should be sorted."""
        output = "1.158.0\n1.155.0\n1.157.0"
        result = discover.parse_existing_tags(output)
        assert result == ["1.155.0", "1.157.0", "1.158.0"]


class TestSelectVersions:
    def test_filters_below_min_version(self):
        """Versions below min_version should be excluded."""
        releases = ["1.0.0", "1.1.0", "1.2.0"]
        existing = []
        result = discover.select_versions(releases, existing, min_version="1.1.0")
        assert result == ["1.1.0", "1.2.0"]

    def test_skips_existing(self):
        """Versions in existing list should be excluded."""
        releases = ["1.0.0", "1.1.0", "1.2.0"]
        existing = ["1.1.0"]
        result = discover.select_versions(releases, existing)
        assert result == ["1.0.0", "1.2.0"]

    def test_cap_applied(self):
        """Output should be limited to max_per_run."""
        releases = ["1.0.0", "1.1.0", "1.2.0", "1.3.0", "1.4.0", "1.5.0"]
        existing = []
        result = discover.select_versions(releases, existing, max_per_run=3)
        assert len(result) <= 3

    def test_output_ascending(self):
        """Results should be sorted ascending."""
        releases = ["1.2.0", "1.0.0", "1.1.0"]
        existing = []
        result = discover.select_versions(releases, existing)
        assert result == ["1.0.0", "1.1.0", "1.2.0"]

    def test_semver_comparison_with_different_digit_counts(self):
        """
        Versions with different digit counts should be compared semantically, not as strings.
        String comparison would incorrectly say "1.9.0" >= "1.10.0" is True.
        """
        releases = ["1.9.0", "1.10.0", "1.2.0"]
        existing = []
        result = discover.select_versions(releases, existing, min_version="1.10.0")
        assert result == ["1.10.0"], f"Expected [1.10.0], got {result}"

    def test_force_includes_existing(self):
        """
        With force=True, versions in existing list should be included.
        """
        releases = ["1.158.0"]
        existing = ["1.158.0"]
        result = discover.select_versions(releases, existing, force=True)
        assert result == ["1.158.0"], f"Expected [1.158.0] with force=True, got {result}"

    def test_force_false_excludes_existing(self):
        """
        With force=False (default), versions in existing list should be excluded.
        """
        releases = ["1.158.0"]
        existing = ["1.158.0"]
        result = discover.select_versions(releases, existing, force=False)
        assert result == [], f"Expected [] with force=False, got {result}"
