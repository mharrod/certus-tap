"""Light profile implementation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import dagger

from security_module.constants import ARTIFACT_ROOT, EXCLUDES, MODULE_ROOT
from security_module.manifest import ManifestProfileConfig
from security_module.tooling import (
    TRIVY_SKIP_DIRS,
    ToolCommand,
    build_manifest_metadata,
    resolve_tools,
)

SOURCE_MOUNT = "/src"
ASSETS_MOUNT = "/privacy-pack"
OPENGREP_RULES = "dagger_modules/security/config/semgrep-baseline.yml"
TRIVY_VERSION = "0.54.1"
SYFT_VERSION = "1.17.0"
COSIGN_VERSION = "2.2.2"
TRIVY_BIN = "/usr/local/bin/trivy"
OPENGREP_BIN = "/usr/local/bin/opengrep"
SYFT_BIN = "/usr/local/bin/syft"
COSIGN_BIN = "/usr/local/bin/cosign"
TRIVY_CACHE = "/tmp/trivy-cache"
# Paths to utility scripts
SCRIPTS_DIR = "/module-scripts"
PRIVACY_SCRIPT_PATH = Path(MODULE_ROOT) / "security_module" / "scripts" / "privacy_scan.py"
SUMMARY_SCRIPT_PATH = Path(MODULE_ROOT) / "security_module" / "scripts" / "generate_summary.py"
EMBED_MANIFEST_SCRIPT = Path(MODULE_ROOT) / "security_module" / "scripts" / "embed_manifest_metadata.py"
POLICY_SCRIPT_PATH = Path(MODULE_ROOT) / "security_module" / "scripts" / "enforce_policy.py"
DAST_SCRIPT_PATH = Path(MODULE_ROOT) / "security_module" / "scripts" / "run_dast_placeholder.py"
DEFAULT_STACK_BASE_URL = "http://localhost:8005"

PIP_TOOLCHAIN = [
    "pip",
    "install",
    "--no-cache-dir",
    "--upgrade",
    "pip",
    "ruff",
    "bandit",
    "detect-secrets",
]

# Node.js/JavaScript toolchain
NODE_PACKAGES = [
    "eslint@8.57.0",
    "eslint-plugin-security@1.7.1",
    "@microsoft/eslint-formatter-sarif@3.0.0",
    "retire@5.4.0",
]

NPM_INSTALL = f"""
set -euo pipefail
apt-get install -y nodejs npm
npm install -g {" ".join(NODE_PACKAGES)}
"""

OPENGREP_INSTALL = """
set -euo pipefail
curl -fsSL https://raw.githubusercontent.com/opengrep/opengrep/main/install.sh | bash
ln -sf "$HOME/.opengrep/cli/latest/opengrep" /usr/local/bin/opengrep
chmod +x /usr/local/bin/opengrep
"""

TRIVY_INSTALL = f"""
set -euo pipefail
mkdir -p /tmp/trivy-install
cd /tmp/trivy-install
curl -fsSL https://github.com/aquasecurity/trivy/releases/download/v{TRIVY_VERSION}/trivy_{TRIVY_VERSION}_Linux-64bit.tar.gz -o trivy.tgz
tar -xzf trivy.tgz
mv trivy /usr/local/bin/trivy
chmod +x /usr/local/bin/trivy
rm -rf /tmp/trivy-install
"""

SYFT_INSTALL = f"""
set -euo pipefail
mkdir -p /tmp/syft-install
cd /tmp/syft-install
curl -fsSL https://github.com/anchore/syft/releases/download/v{SYFT_VERSION}/syft_{SYFT_VERSION}_linux_amd64.tar.gz -o syft.tgz
tar -xzf syft.tgz
mv syft /usr/local/bin/syft
chmod +x /usr/local/bin/syft
rm -rf /tmp/syft-install
"""

COSIGN_INSTALL = f"""
set -euo pipefail
mkdir -p /tmp/cosign-install
cd /tmp/cosign-install
curl -fsSL https://github.com/sigstore/cosign/releases/download/v{COSIGN_VERSION}/cosign-linux-amd64 -o cosign
mv cosign /usr/local/bin/cosign
chmod +x /usr/local/bin/cosign
rm -rf /tmp/cosign-install
"""


class LightProfilePipeline:
    def __init__(
        self,
        client: dagger.Client,
        source: dagger.Directory,
        assets: dagger.Directory | None,
        artifact_root: str = ARTIFACT_ROOT,
        skip_privacy_scan: bool = False,
        bundle_id: str = "",
        profile: str = "light",
        manifest_profile: ManifestProfileConfig | None = None,
        selected_tools: list[str] | None = None,
        unsupported_manifest_tools: list[str] | None = None,
        stack_env: Mapping[str, str] | None = None,
        stack_services: Sequence[tuple[str, dagger.Service]] | None = None,
        stack_base_url: str | None = None,
    ) -> None:
        self._client = client
        self._source = source
        self._assets = assets
        self._artifact_root = artifact_root
        self._skip_privacy_scan = skip_privacy_scan
        self._bundle_id = bundle_id
        self._profile = profile
        self._manifest_profile = manifest_profile
        if selected_tools is not None:
            self._selected_tools = selected_tools
            self._unsupported_manifest_tools = unsupported_manifest_tools or []
        else:
            selected, unsupported = resolve_tools(profile, manifest_profile)
            self._selected_tools = selected
            self._unsupported_manifest_tools = unsupported
        self._stack_env = dict(stack_env or {})
        self._stack_services = list(stack_services or [])
        self._stack_base_url = stack_base_url or DEFAULT_STACK_BASE_URL

    def build(self) -> dagger.Directory:
        container = self._prepare_toolchain()
        container = self._run_light_profile(container)
        return container.directory(self._artifact_root)

    def _prepare_toolchain(self) -> dagger.Container:
        # Mount the module's scripts directory
        scripts_dir = self._client.host().directory(
            str(MODULE_ROOT / "security_module" / "scripts"),
            include=["*.py"],
        )

        # Check if JavaScript tools are needed
        needs_js = any(tool in self._selected_tools for tool in ["eslint-security", "retire-js"])

        container = (
            self._client.container()
            .from_("python:3.11-slim")
            .with_env_variable("PIP_DISABLE_PIP_VERSION_CHECK", "1")
            .with_env_variable("PIP_NO_CACHE_DIR", "1")
            .with_env_variable("PYTHONUNBUFFERED", "1")
            .with_workdir(SOURCE_MOUNT)
            .with_mounted_directory(SOURCE_MOUNT, self._source)
            .with_mounted_directory(SCRIPTS_DIR, scripts_dir)
        )
        container = (
            container.with_exec(["apt-get", "update"])
            .with_exec([
                "apt-get",
                "install",
                "-y",
                "bash",
                "curl",
                "git",
                "ca-certificates",
                "tar",
                "gzip",
            ])
            .with_exec(PIP_TOOLCHAIN)
            .with_exec(["bash", "-c", OPENGREP_INSTALL])
            .with_exec(["bash", "-c", TRIVY_INSTALL])
            .with_exec(["bash", "-c", SYFT_INSTALL])
            .with_exec(["bash", "-c", COSIGN_INSTALL])
            .with_env_variable("TRIVY_CACHE_DIR", TRIVY_CACHE)
        )

        # Install Node.js tooling if needed
        if needs_js:
            container = container.with_exec(["bash", "-c", NPM_INSTALL])
        if self._assets is not None:
            container = container.with_mounted_directory(ASSETS_MOUNT, self._assets)
        for key, value in self._stack_env.items():
            container = container.with_env_variable(key, value)
        for name, service in self._stack_services:
            container = container.with_service_binding(name, service)
        return container

    def _run_light_profile(self, container: dagger.Container) -> dagger.Container:
        artifact = self._artifact_root
        container = container.with_exec([
            "python",
            "-c",
            (f"import pathlib; pathlib.Path('{artifact}').mkdir(parents=True, exist_ok=True)"),
        ])

        skip_dirs = {entry.split("/")[0] for entry in EXCLUDES}
        skip_dirs.update(TRIVY_SKIP_DIRS)
        skip_flags = " ".join(f"--skip-dirs {path}" for path in sorted(skip_dirs))

        commands: list[ToolCommand] = []

        if "ruff" in self._selected_tools:
            commands.append(
                ToolCommand(
                    "ruff",
                    [
                        "bash",
                        "-c",
                        f"ruff check --output-format concise . > {artifact}/ruff.txt || true",
                    ],
                    "Python-focused lint (Ruff)",
                )
            )
        bandit_target = "."
        if self._profile == "smoke":
            bandit_target = "dagger_modules/security"

        if "bandit" in self._selected_tools:
            commands.append(
                ToolCommand(
                    "bandit",
                    [
                        "bash",
                        "-c",
                        f"bandit -q -r {bandit_target} -f json -o {artifact}/bandit.json || true",
                    ],
                    "Bandit security analysis",
                )
            )
        if "opengrep" in self._selected_tools:
            commands.append(
                ToolCommand(
                    "opengrep",
                    [
                        "bash",
                        "-c",
                        (
                            f"{OPENGREP_BIN} scan --config {OPENGREP_RULES} "
                            f"--sarif-output={artifact}/opengrep.sarif.json . || true"
                        ),
                    ],
                    "Opengrep baseline rules",
                )
            )
        if "detect-secrets" in self._selected_tools:
            commands.append(
                ToolCommand(
                    "detect-secrets",
                    [
                        "bash",
                        "-c",
                        f"detect-secrets scan --all-files --force-use-all-plugins > {artifact}/detect-secrets.json || true",
                    ],
                    "detect-secrets scan",
                )
            )
        if "trivy" in self._selected_tools:
            commands.append(
                ToolCommand(
                    "trivy",
                    [
                        "bash",
                        "-c",
                        (
                            f"{TRIVY_BIN} fs --scanners vuln,secret,misconfig "
                            f"{skip_flags} --timeout 15m "
                            f"--format sarif --output {artifact}/trivy.sarif.json . || true"
                        ),
                    ],
                    "Trivy filesystem scan",
                )
            )

        if "privacy" in self._selected_tools and not self._skip_privacy_scan and self._assets is not None:
            commands.append(
                ToolCommand(
                    "privacy",
                    [
                        "python",
                        f"{SCRIPTS_DIR}/privacy_scan.py",
                        ASSETS_MOUNT,
                        self._artifact_root,
                    ],
                    "Sample privacy detection",
                )
            )

        if "eslint-security" in self._selected_tools:
            commands.append(
                ToolCommand(
                    "eslint-security",
                    [
                        "bash",
                        "-c",
                        (
                            f"eslint --plugin security --format @microsoft/eslint-formatter-sarif "
                            f"--output-file {artifact}/eslint-security.sarif.json "
                            f". || true"
                        ),
                    ],
                    "ESLint security scanning",
                )
            )

        if "retire-js" in self._selected_tools:
            commands.append(
                ToolCommand(
                    "retire-js",
                    [
                        "bash",
                        "-c",
                        f"retire --outputformat json --outputpath {artifact}/retire.json . || true",
                    ],
                    "Retire.js vulnerable library detection",
                )
            )

        if "sbom" in self._selected_tools:
            # Generate SPDX SBOM
            commands.append(
                ToolCommand(
                    "sbom-spdx",
                    [
                        "bash",
                        "-c",
                        f"{SYFT_BIN} scan dir:. -o spdx-json={artifact}/sbom.spdx.json || true",
                    ],
                    "SBOM generation (SPDX format)",
                )
            )
            # Generate CycloneDX SBOM
            commands.append(
                ToolCommand(
                    "sbom-cyclonedx",
                    [
                        "bash",
                        "-c",
                        f"{SYFT_BIN} scan dir:. -o cyclonedx-json={artifact}/sbom.cyclonedx.json || true",
                    ],
                    "SBOM generation (CycloneDX format)",
                )
            )
        if "dast" in self._selected_tools:
            base_url = self._stack_env.get("STACK_BASE_URL", self._stack_base_url)
            commands.append(
                ToolCommand(
                    "dast",
                    [
                        "python",
                        f"{SCRIPTS_DIR}/run_dast_placeholder.py",
                        self._artifact_root,
                        base_url,
                    ],
                    "DAST placeholder scan",
                )
            )

        executed: list[str] = []
        skipped: list[str] = []

        for command in commands:
            if command.name == "privacy" and (self._skip_privacy_scan or self._assets is None):
                skipped.append(command.name)
                continue
            container = container.with_exec(list(command.command))
            executed.append(command.name)

        # Generate summary using the external script
        container = container.with_exec([
            "python",
            f"{SCRIPTS_DIR}/generate_summary.py",
            artifact,
            json.dumps(executed),
            json.dumps(skipped),
            self._bundle_id,
        ])

        # Generate in-toto attestation if requested
        if "attestation" in self._selected_tools:
            container = container.with_exec([
                "python",
                f"{SCRIPTS_DIR}/generate_attestation.py",
                artifact,
                json.dumps(executed),
                self._bundle_id,
            ])
            executed.append("attestation")

        container = self._write_manifest_metadata(container)
        return container

    def _write_manifest_metadata(self, container: dagger.Container) -> dagger.Container:
        if not self._manifest_profile:
            return container

        metadata = build_manifest_metadata(
            manifest_profile=self._manifest_profile,
            profile_name=self._profile,
            selected_tools=self._selected_tools,
            unsupported=self._unsupported_manifest_tools,
        )

        container = container.with_new_file(
            f"{self._artifact_root}/manifest-info.json",
            json.dumps(metadata, indent=2),
        )

        container = container.with_exec([
            "python",
            f"{SCRIPTS_DIR}/embed_manifest_metadata.py",
            self._artifact_root,
            json.dumps(metadata),
        ])
        if metadata.get("policy_thresholds"):
            container = container.with_exec([
                "python",
                f"{SCRIPTS_DIR}/enforce_policy.py",
                self._artifact_root,
                json.dumps(metadata["policy_thresholds"]),
            ])
        return container
