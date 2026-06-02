"""CI check: committed data must match the SHA256 checksums in the data manifest.

This runs in the normal pytest suite (and therefore in CI on every push/PR), so
the committed checksums become an active, automatic data-integrity gate.
"""

from preprocessing.build_data_manifest import PROJECT_ROOT, verify_data_manifest


def test_committed_data_matches_manifest_checksums() -> None:
    manifest_path = PROJECT_ROOT / "data" / "processed" / "manifests" / "data_manifest.json"
    assert manifest_path.exists(), "committed data manifest is missing"
    assert verify_data_manifest(manifest_path=manifest_path, strict=False) == []
