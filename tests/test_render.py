"""
Test rendering of the Config Connector Helm chart.
"""

import copy


def normalize_for_comparison(doc):
    """
    Remove Helm-added labels and annotations for comparison.
    """
    doc = copy.deepcopy(doc)
    if "metadata" in doc:
        if "labels" in doc["metadata"]:
            doc["metadata"]["labels"].pop("app.kubernetes.io/managed-by", None)
            doc["metadata"]["labels"].pop("helm.sh/chart", None)
            doc["metadata"]["labels"].pop("app.kubernetes.io/name", None)
            doc["metadata"]["labels"].pop("app.kubernetes.io/instance", None)
            doc["metadata"]["labels"].pop("app.kubernetes.io/version", None)
            if not doc["metadata"]["labels"]:
                doc["metadata"].pop("labels", None)
        if "annotations" in doc["metadata"]:
            doc["metadata"]["annotations"].pop("helm.sh/resource-policy", None)
            if not doc["metadata"]["annotations"]:
                doc["metadata"].pop("annotations", None)
    return doc


class TestDefaultRender:
    def test_default_render_matches_upstream(self, helm_template, upstream_manifest):
        """
        Render with default values and compare to upstream.
        Each upstream object (except Namespace) should appear in rendered output
        with only Helm-managed labels/annotations differing.
        """
        rendered = helm_template()

        # Build lookup tables
        upstream_by_key = {}
        for doc in upstream_manifest:
            if doc.get("kind") != "Namespace":
                key = (doc.get("kind"), doc.get("metadata", {}).get("name"))
                upstream_by_key[key] = doc

        rendered_by_key = {}
        for doc in rendered:
            key = (doc.get("kind"), doc.get("metadata", {}).get("name"))
            rendered_by_key[key] = doc

        # Check all upstream objects are present
        for key in upstream_by_key:
            assert key in rendered_by_key, f"Missing object {key}"

        # Check normalized content matches
        for key, upstream_doc in upstream_by_key.items():
            rendered_doc = rendered_by_key[key]
            assert normalize_for_comparison(upstream_doc) == normalize_for_comparison(
                rendered_doc
            ), f"Mismatch in {key}"

        # Check no extra objects in rendered output
        assert set(rendered_by_key.keys()) == set(upstream_by_key.keys()), (
            f"Extra objects in render: {set(rendered_by_key.keys()) - set(upstream_by_key.keys())}"
        )


class TestImageOverrides:
    def test_overrides_image_tag(self, helm_template):
        """
        Override image tag and verify it's applied to the StatefulSet.
        """
        docs = helm_template(set_values={"image.tag": "9.9.9"})

        ss = next((d for d in docs if d.get("kind") == "StatefulSet"), None)
        assert ss is not None, "StatefulSet not found"

        container = ss["spec"]["template"]["spec"]["containers"][0]
        assert container["image"].endswith(":9.9.9"), (
            f"Image tag not overridden: {container['image']}"
        )


class TestResourceOverrides:
    def test_overrides_resources(self, helm_template):
        """
        Override container resources and verify they're applied.
        """
        docs = helm_template(
            set_values={"resources.requests.cpu": "200m", "resources.limits.memory": "2Gi"}
        )

        ss = next((d for d in docs if d.get("kind") == "StatefulSet"), None)
        assert ss is not None

        container = ss["spec"]["template"]["spec"]["containers"][0]
        assert container.get("resources", {}).get("requests", {}).get("cpu") == "200m"
        assert container.get("resources", {}).get("limits", {}).get("memory") == "2Gi"


class TestNodeSelection:
    def test_overrides_node_selector(self, helm_template):
        """
        Set nodeSelector and verify it's applied to pod spec.
        """
        docs = helm_template(set_values={"nodeSelector.disktype": "ssd"})

        ss = next((d for d in docs if d.get("kind") == "StatefulSet"), None)
        assert ss is not None

        pod_spec = ss["spec"]["template"]["spec"]
        assert pod_spec.get("nodeSelector", {}).get("disktype") == "ssd"


class TestPodLabels:
    def test_pod_labels_not_in_selector(self, helm_template):
        """
        Set podLabels and verify they appear in pod template but NOT in StatefulSet selector.
        """
        docs = helm_template(set_values={"podLabels.custom": "value"})

        ss = next((d for d in docs if d.get("kind") == "StatefulSet"), None)
        assert ss is not None

        pod_labels = ss["spec"]["template"]["metadata"].get("labels", {})
        assert pod_labels.get("custom") == "value", "podLabel not in pod template"

        selector_labels = ss["spec"]["selector"]["matchLabels"]
        assert "custom" not in selector_labels, "podLabel incorrectly in selector"


class TestCRDHandling:
    def test_crds_enabled_false(self, helm_template):
        """
        With crds.enabled=false, no CRD objects should be rendered.
        """
        docs = helm_template(set_values={"crds.enabled": "false"})

        crds = [d for d in docs if d.get("kind") == "CustomResourceDefinition"]
        assert len(crds) == 0, f"Found {len(crds)} CRDs when crds.enabled=false"

    def test_crds_keep_true(self, helm_template):
        """
        With crds.keep=true, all CRDs should have helm.sh/resource-policy: keep annotation.
        """
        docs = helm_template(set_values={"crds.keep": "true"})

        crds = [d for d in docs if d.get("kind") == "CustomResourceDefinition"]
        assert len(crds) > 0, "No CRDs found in render"

        for crd in crds:
            annotations = crd.get("metadata", {}).get("annotations", {})
            assert annotations.get("helm.sh/resource-policy") == "keep", (
                f"CRD {crd['metadata']['name']} missing keep annotation"
            )

    def test_crds_keep_false(self, helm_template):
        """
        With crds.keep=false, CRDs should NOT have the keep annotation.
        """
        docs = helm_template(set_values={"crds.keep": "false"})

        crds = [d for d in docs if d.get("kind") == "CustomResourceDefinition"]

        for crd in crds:
            annotations = crd.get("metadata", {}).get("annotations", {})
            # Check that 'keep' annotation is NOT set (or is not our keep value)
            if "helm.sh/resource-policy" in annotations:
                assert annotations["helm.sh/resource-policy"] != "keep"


class TestNamespace:
    def test_no_namespace_object(self, helm_template):
        """
        No Namespace object should be rendered (we skip it).
        """
        docs = helm_template()

        namespaces = [d for d in docs if d.get("kind") == "Namespace"]
        assert len(namespaces) == 0, "Namespace object found in render"
