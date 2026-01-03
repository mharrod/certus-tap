import json
from pathlib import Path

from security_module.scripts import embed_manifest_metadata


def test_embed_manifest_metadata_writes_general_block(tmp_path):
    artifact_dir = Path(tmp_path)
    bandit_file = artifact_dir / "bandit.json"
    bandit_file.write_text(json.dumps({"results": []}))

    metadata = {"product": "tap", "profile_requested": "light"}
    embed_manifest_metadata.main(str(artifact_dir), json.dumps(metadata))

    data = json.loads(bandit_file.read_text())
    assert data["_certus_manifest"]["product"] == "tap"
    assert data["_certus_manifest"]["profile_requested"] == "light"
