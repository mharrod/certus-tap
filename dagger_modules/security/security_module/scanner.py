"""Runtime-agnostic security scanner orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from security_module.manifest import (
    ManifestProfileConfig,
    load_manifest_from_json,
    load_manifest_from_path,
)
from security_module.runtime import RuntimeResult, ScanRequest, ScanRuntime
from security_module.tooling import profile_requires_stack, resolve_tools, validate_profile_name

DEFAULT_STACK_BASE_URL = "http://localhost:8005"


class SecurityScanner:
    """High-level facade that loads manifests and dispatches to runtimes."""

    def __init__(self, runtime: ScanRuntime) -> None:
        self._runtime = runtime

    async def run(
        self,
        *,
        profile: str,
        workspace: str | Path | None = None,
        source: Any | None = None,
        export_dir: str | Path | None = None,
        manifest_path: str | None = None,
        manifest_text: str | None = None,
        bundle_id: str | None = None,
        skip_privacy_scan: bool = False,
        privacy_assets: Any | None = None,
    ) -> RuntimeResult:
        manifest_profile = self._load_manifest(manifest_path, manifest_text, profile)
        validate_profile_name(profile, has_manifest=manifest_profile is not None)
        selected_tools, unsupported = resolve_tools(profile, manifest_profile)
        requires_stack = profile_requires_stack(profile, manifest_profile, selected_tools)
        stack_base_url = manifest_profile.raw_profile.get("stackBaseUrl") if manifest_profile else None
        if stack_base_url is None and requires_stack:
            stack_base_url = DEFAULT_STACK_BASE_URL

        workspace_path = self._resolve_path(workspace)
        export_path = self._resolve_path(export_dir)
        source_ref = source if source is not None else workspace_path
        privacy_ref = self._resolve_privacy_assets(privacy_assets)

        request = ScanRequest(
            profile=profile,
            selected_tools=selected_tools,
            unsupported_manifest_tools=unsupported,
            workspace=workspace_path,
            source=source_ref,
            export_dir=export_path,
            bundle_id=bundle_id,
            manifest_profile=manifest_profile,
            skip_privacy_scan=skip_privacy_scan,
            privacy_assets=privacy_ref,
            requires_stack=requires_stack,
            stack_base_url=stack_base_url,
        )
        return await self._runtime.run(request)

    def _load_manifest(
        self,
        manifest_path: str | None,
        manifest_text: str | None,
        profile: str,
    ) -> ManifestProfileConfig | None:
        if manifest_path:
            return load_manifest_from_path(manifest_path, profile)
        if manifest_text:
            return load_manifest_from_json(manifest_text, profile)
        return None

    def _resolve_path(self, value: str | Path | None) -> Path | None:
        if value is None:
            return None
        return Path(value).expanduser().resolve()

    def _resolve_privacy_assets(self, value: Any | None) -> Any | None:
        if value is None:
            return None
        if isinstance(value, (str, Path)):
            return Path(value).expanduser().resolve()
        return value
