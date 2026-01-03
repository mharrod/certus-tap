from security_module.manifest import (
    ManifestProfileConfig,
    load_manifest_from_json,
)


def test_load_manifest_extracts_tools():
    manifest_text = """
    {
        "product": "certus-tap",
        "version": "1.0.0",
        "profiles": [
            {
                "name": "light",
                "tools": [
                    "ruff",
                    {"id": "bandit"},
                    {"name": "detect-secrets"},
                    {"id": "unsupported-tool"}
                ]
            }
        ]
    }
    """

    config = load_manifest_from_json(manifest_text, "light")

    assert isinstance(config, ManifestProfileConfig)
    assert config.product == "certus-tap"
    assert config.version == "1.0.0"
    assert config.profile_name == "light"
    assert config.tools == [
        "ruff",
        "bandit",
        "detect-secrets",
        "unsupported-tool",
    ]
    assert config.digest
