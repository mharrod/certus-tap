"""Runtime abstractions for executing security scans."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

import dagger
from dagger import dag

from security_module import policy
from security_module.artifacts import ensure_export_dir
from security_module.constants import ARTIFACT_ROOT, DEFAULT_EXPORT_DIR, EXCLUDES, MODULE_ROOT, PRIVACY_SAMPLE_DIR
from security_module.manifest import ManifestProfileConfig
from security_module.sast import LightProfilePipeline
from security_module.tooling import (
    ATTESTATION_SCRIPT_PATH,
    PRIVACY_SCRIPT_PATH,
    SUMMARY_SCRIPT_PATH,
    TRIVY_SKIP_DIRS,
    ToolCommand,
    build_manifest_metadata,
)

DAST_SCRIPT_PATH = MODULE_ROOT / "security_module" / "scripts" / "run_dast_placeholder.py"
STACK_DEFAULT_BASE_URL = "http://localhost:8005"
LogSink = Callable[[str, dict[str, Any]], None] | None


@dataclass(slots=True)
class ScanRequest:
    """Bundle of parameters passed into runtime implementations."""

    profile: str
    selected_tools: list[str]
    unsupported_manifest_tools: list[str]
    workspace: Path | None = None
    source: Any | None = None
    privacy_assets: Any | None = None
    export_dir: Path | None = None
    bundle_id: str | None = None
    manifest_profile: ManifestProfileConfig | None = None
    skip_privacy_scan: bool = False
    requires_stack: bool = False
    stack_base_url: str | None = None


@dataclass(slots=True)
class RuntimeResult:
    """Result information returned by runtime implementations."""

    bundle_id: str
    artifacts: Any
    export_dir: Path | None = None
    policy_passed: bool | None = None
    policy_violations: list[str] | None = None


class ScanRuntime(Protocol):
    """Protocol implemented by every runtime."""

    async def run(self, request: ScanRequest) -> RuntimeResult: ...


def _derive_bundle_id(workspace: Path) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(workspace),
            check=True,
            capture_output=True,
            text=True,
        )
        sha = result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        sha = ""
    suffix = f"-{sha}" if sha else ""
    return f"{timestamp}{suffix}"


class LocalRuntime:
    """Execute scans directly on the host using installed tooling."""

    def __init__(self, *, log_sink: LogSink = None) -> None:
        self._log_sink = log_sink

    async def run(self, request: ScanRequest) -> RuntimeResult:
        if request.workspace is None:
            raise ValueError("LocalRuntime requires workspace path")

        workspace = request.workspace
        export_root = ensure_export_dir(request.export_dir or DEFAULT_EXPORT_DIR)
        bundle_id = request.bundle_id or _derive_bundle_id(workspace)
        bundle_path = export_root / bundle_id
        bundle_path.mkdir(parents=True, exist_ok=True)

        artifact_dir = bundle_path
        stack_base_url = request.stack_base_url or STACK_DEFAULT_BASE_URL
        commands = self._build_commands(request, artifact_dir, stack_base_url)

        executed: list[str] = []
        skipped: list[str] = []
        for command in commands:
            if command.name == "privacy" and request.skip_privacy_scan:
                skipped.append(command.name)
                continue
            return_code = await self._run_command(command.command, cwd=workspace, name=command.name)
            if return_code != 0:
                print(f"[security] tool '{command.name}' exited with code {return_code}", file=sys.stderr)
            executed.append(command.name)

        await self._run_summary(artifact_dir, executed, skipped, bundle_id, workspace)

        if "attestation" in request.selected_tools:
            await self._run_command(
                [
                    "python",
                    str(ATTESTATION_SCRIPT_PATH),
                    str(artifact_dir),
                    json.dumps(executed),
                    bundle_id,
                ],
                cwd=workspace,
                name="attestation",
            )

        if request.manifest_profile:
            metadata = build_manifest_metadata(
                manifest_profile=request.manifest_profile,
                profile_name=request.profile,
                selected_tools=request.selected_tools,
                unsupported=request.unsupported_manifest_tools,
            )
            (artifact_dir / "manifest-info.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            await self._run_command(
                [
                    "python",
                    str(MODULE_ROOT / "security_module" / "scripts" / "embed_manifest_metadata.py"),
                    str(artifact_dir),
                    json.dumps(metadata),
                ],
                cwd=workspace,
                name="manifest-embed",
            )
            if metadata.get("policy_thresholds"):
                violations = policy.enforce_thresholds(artifact_dir, metadata["policy_thresholds"])
                if violations:
                    raise RuntimeError("; ".join(violations))

        return RuntimeResult(bundle_id=bundle_id, artifacts=artifact_dir, export_dir=export_root)

    async def _run_command(self, command: list[str], cwd: Path, *, name: str | None = None) -> int:
        if self._log_sink and name:
            self._log_sink("tool_start", {"tool": name, "command": command})
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait([
            asyncio.create_task(self._forward_stream(process.stdout, name, "stdout")),
            asyncio.create_task(self._forward_stream(process.stderr, name, "stderr")),
        ])
        code = await process.wait()
        if self._log_sink and name:
            self._log_sink("tool_complete", {"tool": name, "exit_code": code})
        return code or 0

    async def _forward_stream(self, stream: asyncio.StreamReader | None, tool: str | None, stream_name: str) -> None:
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode(errors="replace").rstrip()
            if stream_name == "stderr":
                print(text, file=sys.stderr)
            else:
                print(text)
            if self._log_sink and tool:
                self._log_sink(
                    "log",
                    {
                        "tool": tool,
                        "stream": stream_name,
                        "line": text,
                    },
                )

    async def _run_summary(
        self,
        artifact_dir: Path,
        executed: list[str],
        skipped: list[str],
        bundle_id: str,
        workspace: Path,
    ) -> None:
        await self._run_command(
            [
                "python",
                str(SUMMARY_SCRIPT_PATH),
                str(artifact_dir),
                json.dumps(executed),
                json.dumps(skipped),
                bundle_id,
            ],
            cwd=workspace,
            name="summary",
        )

    def _build_commands(self, request: ScanRequest, artifact_dir: Path, stack_base_url: str) -> list[ToolCommand]:
        commands: list[ToolCommand] = []
        workspace = request.workspace or Path(".")
        skip_dirs = {entry.split("/")[0] for entry in EXCLUDES}
        skip_dirs.update(TRIVY_SKIP_DIRS)
        skip_flags = " ".join(f"--skip-dirs {path}" for path in sorted(skip_dirs))

        if "ruff" in request.selected_tools:
            commands.append(
                ToolCommand(
                    "ruff",
                    [
                        "bash",
                        "-c",
                        f"ruff check --output-format concise . > {artifact_dir}/ruff.txt || true",
                    ],
                    "Python-focused lint (Ruff)",
                )
            )
        bandit_target = "." if request.profile != "smoke" else "dagger_modules/security"
        if "bandit" in request.selected_tools:
            commands.append(
                ToolCommand(
                    "bandit",
                    [
                        "bash",
                        "-c",
                        f"bandit -q -r {bandit_target} -f json -o {artifact_dir}/bandit.json || true",
                    ],
                    "Bandit security analysis",
                )
            )
        if "opengrep" in request.selected_tools:
            rules = MODULE_ROOT / "config" / "semgrep-baseline.yml"
            commands.append(
                ToolCommand(
                    "opengrep",
                    [
                        "bash",
                        "-c",
                        (f"opengrep scan --config {rules} --sarif-output={artifact_dir}/opengrep.sarif.json . || true"),
                    ],
                    "Opengrep baseline rules",
                )
            )
        if "detect-secrets" in request.selected_tools:
            commands.append(
                ToolCommand(
                    "detect-secrets",
                    [
                        "bash",
                        "-c",
                        f"detect-secrets scan --all-files --force-use-all-plugins > {artifact_dir}/detect-secrets.json || true",
                    ],
                    "detect-secrets scan",
                )
            )
        if "trivy" in request.selected_tools:
            commands.append(
                ToolCommand(
                    "trivy",
                    [
                        "bash",
                        "-c",
                        (
                            "trivy fs --scanners vuln,secret,misconfig "
                            f"{skip_flags} --timeout 15m "
                            f"--format sarif --output {artifact_dir}/trivy.sarif.json . || true"
                        ),
                    ],
                    "Trivy filesystem scan",
                )
            )

        privacy_assets = self._resolve_privacy_assets(request)
        if "privacy" in request.selected_tools and not request.skip_privacy_scan and privacy_assets:
            commands.append(
                ToolCommand(
                    "privacy",
                    [
                        "python",
                        str(PRIVACY_SCRIPT_PATH),
                        str(privacy_assets),
                        str(artifact_dir),
                    ],
                    "Sample privacy detection",
                )
            )

        if "eslint-security" in request.selected_tools:
            commands.append(
                ToolCommand(
                    "eslint-security",
                    [
                        "bash",
                        "-c",
                        (
                            "eslint --plugin security --format @microsoft/eslint-formatter-sarif "
                            f"--output-file {artifact_dir}/eslint-security.sarif.json "
                            ". || true"
                        ),
                    ],
                    "ESLint security scanning",
                )
            )

        if "retire-js" in request.selected_tools:
            commands.append(
                ToolCommand(
                    "retire-js",
                    [
                        "bash",
                        "-c",
                        f"retire --outputformat json --outputpath {artifact_dir}/retire.json . || true",
                    ],
                    "Retire.js vulnerable library detection",
                )
            )

        if "sbom" in request.selected_tools:
            commands.append(
                ToolCommand(
                    "sbom-spdx",
                    [
                        "bash",
                        "-c",
                        f"syft scan dir:. -o spdx-json={artifact_dir}/sbom.spdx.json || true",
                    ],
                    "SBOM generation (SPDX format)",
                )
            )
            commands.append(
                ToolCommand(
                    "sbom-cyclonedx",
                    [
                        "bash",
                        "-c",
                        f"syft scan dir:. -o cyclonedx-json={artifact_dir}/sbom.cyclonedx.json || true",
                    ],
                    "SBOM generation (CycloneDX format)",
                )
            )
        if "dast" in request.selected_tools:
            commands.append(
                ToolCommand(
                    "dast",
                    [
                        "python",
                        str(DAST_SCRIPT_PATH),
                        str(artifact_dir),
                        stack_base_url,
                    ],
                    "DAST placeholder scan",
                )
            )

        return commands

    def _resolve_privacy_assets(self, request: ScanRequest) -> Path | None:
        if request.privacy_assets and isinstance(request.privacy_assets, Path):
            return request.privacy_assets
        if PRIVACY_SAMPLE_DIR.exists():
            return PRIVACY_SAMPLE_DIR
        return None


class ManagedRuntime(LocalRuntime):
    """Local runtime variant that emits structured events for managed services."""

    def __init__(self, *, log_sink: LogSink | None = None) -> None:
        super().__init__(log_sink=log_sink)


class DaggerRuntime:
    """Execute scans via the LightProfilePipeline using a fresh Dagger connection."""

    def __init__(self, *, log_output: Any | None = None, timeout: float | None = None) -> None:
        self._log_output = log_output
        self._timeout = timeout

    async def run(self, request: ScanRequest) -> RuntimeResult:
        if request.workspace is None:
            raise ValueError("DaggerRuntime requires workspace path")

        export_root = ensure_export_dir(request.export_dir or DEFAULT_EXPORT_DIR)
        bundle_id = request.bundle_id or _derive_bundle_id(request.workspace)
        bundle_path = export_root / bundle_id
        bundle_path.mkdir(parents=True, exist_ok=True)

        config = dagger.Config(log_output=self._log_output, execute_timeout=self._timeout)
        async with dagger.Connection(config) as client:
            src = client.host().directory(str(request.workspace), exclude=EXCLUDES)
            assets_dir = None
            assets_path = request.privacy_assets or PRIVACY_SAMPLE_DIR
            if isinstance(assets_path, Path) and assets_path.exists():
                assets_dir = client.host().directory(str(assets_path))
            stack_env: dict[str, str] = {}
            stack_services: list[tuple[str, dagger.Service]] = []
            stack_base_url = request.stack_base_url
            if request.requires_stack:
                stack_env, stack_services, stack_base_url = await self._bootstrap_stack(client, request.stack_base_url)
            pipeline = LightProfilePipeline(
                client,
                src,
                assets=assets_dir,
                artifact_root=f"{ARTIFACT_ROOT}/{bundle_id}",
                skip_privacy_scan=request.skip_privacy_scan,
                bundle_id=bundle_id,
                profile=request.profile,
                manifest_profile=request.manifest_profile,
                selected_tools=request.selected_tools,
                unsupported_manifest_tools=request.unsupported_manifest_tools,
                stack_env=stack_env,
                stack_services=stack_services,
                stack_base_url=stack_base_url,
            )
            artifacts = pipeline.build()
            await artifacts.export(str(bundle_path))

        # Read policy results if they exist
        policy_passed = None
        policy_violations = None
        policy_file = bundle_path / "policy-result.json"
        if policy_file.exists():
            import json

            try:
                policy_data = json.loads(policy_file.read_text())
                policy_passed = policy_data.get("passed")
                policy_violations = policy_data.get("violations")
            except (json.JSONDecodeError, OSError):
                pass

        return RuntimeResult(
            bundle_id=bundle_id,
            artifacts=bundle_path,
            export_dir=export_root,
            policy_passed=policy_passed,
            policy_violations=policy_violations,
        )

    async def _bootstrap_stack(
        self,
        client: dagger.Connection,
        requested_url: str | None,
    ) -> tuple[dict[str, str], list[tuple[str, dagger.Service]], str]:
        service_name = "stack-service"
        port = "8005"
        service = (
            client.container().from_("python:3.11-slim").with_exec(["python", "-m", "http.server", port]).as_service()
        )
        base_url = requested_url or f"http://{service_name}:{port}"
        env = {"STACK_BASE_URL": base_url}
        return env, [(service_name, service)], base_url


class DaggerModuleRuntime:
    """Execute scans inside the published Dagger module (no host exports by default)."""

    async def run(self, request: ScanRequest) -> RuntimeResult:
        if request.source is None or not isinstance(request.source, dagger.Directory):
            raise ValueError("DaggerModuleRuntime requires dagger.Directory source")

        bundle_id = request.bundle_id or await self._default_bundle_id(request.source)
        stack_env: dict[str, str] = {}
        stack_services: list[tuple[str, dagger.Service]] = []
        stack_base_url = request.stack_base_url
        if request.requires_stack:
            stack_env, stack_services, stack_base_url = self._module_stack_context(request.stack_base_url)
        pipeline = LightProfilePipeline(
            dag,
            request.source,
            assets=request.privacy_assets if isinstance(request.privacy_assets, dagger.Directory) else None,
            artifact_root=f"{ARTIFACT_ROOT}/{bundle_id}",
            skip_privacy_scan=request.skip_privacy_scan,
            bundle_id=bundle_id,
            profile=request.profile,
            manifest_profile=request.manifest_profile,
            selected_tools=request.selected_tools,
            unsupported_manifest_tools=request.unsupported_manifest_tools,
            stack_env=stack_env,
            stack_services=stack_services,
            stack_base_url=stack_base_url,
        )
        artifacts = pipeline.build()

        if request.export_dir:
            export_target = request.export_dir / bundle_id
            await artifacts.export(str(export_target))

        return RuntimeResult(bundle_id=bundle_id, artifacts=artifacts, export_dir=request.export_dir)

    async def _default_bundle_id(self, source: dagger.Directory) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        try:
            git_sha = (
                await dag.container()
                .from_("alpine/git")
                .with_mounted_directory("/src", source)
                .with_workdir("/src")
                .with_exec(["git", "rev-parse", "--short", "HEAD"])
                .stdout()
            ).strip()
        except Exception:
            git_sha = ""
        suffix = f"-{git_sha}" if git_sha else ""
        return f"{timestamp}{suffix}"

    def _module_stack_context(
        self,
        requested_url: str | None,
    ) -> tuple[dict[str, str], list[tuple[str, dagger.Service]], str]:
        service_name = "stack-service"
        port = "8005"
        service = (
            dag.container().from_("python:3.11-slim").with_exec(["python", "-m", "http.server", port]).as_service()
        )
        base_url = requested_url or f"http://{service_name}:{port}"
        env = {"STACK_BASE_URL": base_url}
        return env, [(service_name, service)], base_url
