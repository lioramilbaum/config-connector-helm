"""
Tests for the GitHub Release step in the publish workflow.
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

workflow_path = REPO_ROOT / ".github/workflows/publish.yaml"
with open(workflow_path) as f:
    workflow = yaml.safe_load(f)

publish_job = workflow["jobs"]["publish"]
steps = publish_job["steps"]


def _find_step_index(name):
    for i, step in enumerate(steps):
        if step.get("name") == name:
            return i
    return None


def _release_steps():
    return [s for s in steps if "gh release create" in s.get("run", "")]


class TestPublishPermissions:
    def test_contents_is_write(self):
        """Creating a GitHub Release requires contents: write."""
        assert publish_job["permissions"]["contents"] == "write"


class TestReleaseStep:
    def test_exactly_one_release_step(self):
        """Exactly one step should create the GitHub Release."""
        assert len(_release_steps()) == 1

    def test_generates_notes_and_title(self):
        """Release should use generated notes and a v-prefixed title."""
        run = _release_steps()[0]["run"]
        assert "--generate-notes" in run
        assert '--title "v$VERSION"' in run

    def test_version_env(self):
        """VERSION should come from the resolve-version job output."""
        env = _release_steps()[0]["env"]
        assert env["VERSION"] == "${{ needs.resolve-version.outputs.version }}"

    def test_runs_after_signing_and_verification(self):
        """Release must only be created after the chart is signed and verified."""
        release_index = steps.index(_release_steps()[0])
        assert _find_step_index("Sign chart") is not None
        assert _find_step_index("Verify signature") is not None
        assert release_index > _find_step_index("Sign chart")
        assert release_index > _find_step_index("Verify signature")

    def test_skipped_on_backfill(self):
        """Manual version overrides (backfills) must not create releases."""
        assert _release_steps()[0]["if"] == "inputs.version == ''"

    def test_idempotency_guard(self):
        """Step must skip creation when the release already exists."""
        assert "gh release view" in _release_steps()[0]["run"]
