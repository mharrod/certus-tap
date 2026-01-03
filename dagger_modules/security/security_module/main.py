"""Dagger module entry points."""

from __future__ import annotations

from pathlib import Path

import dagger
from dagger import function, object_type

from security_module.runtime import DaggerModuleRuntime
from security_module.scanner import SecurityScanner


@object_type
class Security:
    """Public Dagger module functions."""

    def __init__(self) -> None:
        self._runtime = DaggerModuleRuntime()

    @function
    async def light(
        self,
        source: dagger.Directory,
        skip_privacy_scan: bool = False,
        privacy_assets: dagger.Directory | None = None,
        bundle_id: str | None = None,
        export_path: str | None = None,
        manifest: dagger.File | None = None,
    ) -> dagger.Directory:
        """Execute the light profile and return artifacts."""
        return await self._run_profile(
            profile="light",
            source=source,
            skip_privacy_scan=skip_privacy_scan,
            privacy_assets=privacy_assets,
            bundle_id=bundle_id,
            export_path=export_path,
            manifest=manifest,
        )

    @function
    async def smoke(
        self,
        source: dagger.Directory,
        skip_privacy_scan: bool = False,
        privacy_assets: dagger.Directory | None = None,
        bundle_id: str | None = None,
        export_path: str | None = None,
        manifest: dagger.File | None = None,
    ) -> dagger.Directory:
        """Execute the smoke profile (Ruff only) - ~20 seconds.

        Minimal health check to verify toolchain works.
        """
        return await self._run_profile(
            profile="smoke",
            source=source,
            skip_privacy_scan=skip_privacy_scan,
            privacy_assets=privacy_assets,
            bundle_id=bundle_id,
            export_path=export_path,
            manifest=manifest,
        )

    @function
    async def fast(
        self,
        source: dagger.Directory,
        skip_privacy_scan: bool = False,
        privacy_assets: dagger.Directory | None = None,
        bundle_id: str | None = None,
        export_path: str | None = None,
        manifest: dagger.File | None = None,
    ) -> dagger.Directory:
        """Execute the fast profile (Ruff + Bandit + detect-secrets) - ~2 minutes.

        Recommended for pre-commit hooks and local development.
        """
        return await self._run_profile(
            profile="fast",
            source=source,
            skip_privacy_scan=skip_privacy_scan,
            privacy_assets=privacy_assets,
            bundle_id=bundle_id,
            export_path=export_path,
            manifest=manifest,
        )

    @function
    async def medium(
        self,
        source: dagger.Directory,
        skip_privacy_scan: bool = False,
        privacy_assets: dagger.Directory | None = None,
        bundle_id: str | None = None,
        export_path: str | None = None,
        manifest: dagger.File | None = None,
    ) -> dagger.Directory:
        """Execute the medium profile (fast + Opengrep + attestation) - ~4 minutes.

        Recommended for pre-push sanity checks. Generates in-toto attestation.
        """
        return await self._run_profile(
            profile="medium",
            source=source,
            skip_privacy_scan=skip_privacy_scan,
            privacy_assets=privacy_assets,
            bundle_id=bundle_id,
            export_path=export_path,
            manifest=manifest,
        )

    @function
    async def standard(
        self,
        source: dagger.Directory,
        skip_privacy_scan: bool = False,
        privacy_assets: dagger.Directory | None = None,
        bundle_id: str | None = None,
        export_path: str | None = None,
        manifest: dagger.File | None = None,
    ) -> dagger.Directory:
        """Execute the standard profile (fast + Trivy + SBOM) - ~10 minutes.

        Recommended for PR gates and CI pipelines. Includes supply chain tracking (SBOM).
        """
        return await self._run_profile(
            profile="standard",
            source=source,
            skip_privacy_scan=skip_privacy_scan,
            privacy_assets=privacy_assets,
            bundle_id=bundle_id,
            export_path=export_path,
            manifest=manifest,
        )

    @function
    async def full(
        self,
        source: dagger.Directory,
        skip_privacy_scan: bool = False,
        privacy_assets: dagger.Directory | None = None,
        bundle_id: str | None = None,
        export_path: str | None = None,
        manifest: dagger.File | None = None,
    ) -> dagger.Directory:
        """Execute the full profile (standard + Opengrep + privacy) - ~15 minutes.

        Comprehensive scan recommended for releases and main branch merges.
        Includes advanced SAST (Opengrep) and privacy detection.
        """
        return await self._run_profile(
            profile="full",
            source=source,
            skip_privacy_scan=skip_privacy_scan,
            privacy_assets=privacy_assets,
            bundle_id=bundle_id,
            export_path=export_path,
            manifest=manifest,
        )

    @function
    async def heavy(
        self,
        source: dagger.Directory,
        skip_privacy_scan: bool = False,
        privacy_assets: dagger.Directory | None = None,
        bundle_id: str | None = None,
        export_path: str | None = None,
        manifest: dagger.File | None = None,
    ) -> dagger.Directory:
        """Execute the heavy profile (full + DAST/API placeholders) - exercises stack bootstrap."""
        return await self._run_profile(
            profile="heavy",
            source=source,
            skip_privacy_scan=skip_privacy_scan,
            privacy_assets=privacy_assets,
            bundle_id=bundle_id,
            export_path=export_path,
            manifest=manifest,
        )

    @function
    async def javascript(
        self,
        source: dagger.Directory,
        skip_privacy_scan: bool = False,
        privacy_assets: dagger.Directory | None = None,
        bundle_id: str | None = None,
        export_path: str | None = None,
        manifest: dagger.File | None = None,
    ) -> dagger.Directory:
        """Execute the JavaScript profile (ESLint security + retire.js + Trivy + SBOM) - ~3 minutes.

        Optimized for Node.js/JavaScript projects like OWASP Juice Shop.
        Includes JavaScript-specific security scanning and vulnerable library detection.
        """
        return await self._run_profile(
            profile="javascript",
            source=source,
            skip_privacy_scan=skip_privacy_scan,
            privacy_assets=privacy_assets,
            bundle_id=bundle_id,
            export_path=export_path,
            manifest=manifest,
        )

    @function
    async def attestation_test(
        self,
        source: dagger.Directory,
        skip_privacy_scan: bool = False,
        privacy_assets: dagger.Directory | None = None,
        bundle_id: str | None = None,
        export_path: str | None = None,
        manifest: dagger.File | None = None,
    ) -> dagger.Directory:
        """Execute attestation test profile (Ruff + SBOM + attestation) - ~30 seconds.

        Quick validation that SBOM generation and in-toto attestation work correctly.
        Useful for testing signing workflows without running full security scans.
        """
        return await self._run_profile(
            profile="attestation-test",
            source=source,
            skip_privacy_scan=skip_privacy_scan,
            privacy_assets=privacy_assets,
            bundle_id=bundle_id,
            export_path=export_path,
            manifest=manifest,
        )

    async def _run_profile(
        self,
        profile: str,
        source: dagger.Directory,
        skip_privacy_scan: bool,
        privacy_assets: dagger.Directory | None,
        bundle_id: str | None,
        export_path: str | None,
        manifest: dagger.File | None = None,
    ) -> dagger.Directory:
        manifest_text: str | None = None
        if manifest is not None:
            contents = await manifest.contents()
            manifest_text = contents.decode("utf-8") if isinstance(contents, bytes) else contents

        scanner = SecurityScanner(self._runtime)
        export_dir = Path(export_path).expanduser().resolve() if export_path else None
        result = await scanner.run(
            profile=profile,
            source=source,
            export_dir=export_dir,
            bundle_id=bundle_id,
            manifest_text=manifest_text,
            skip_privacy_scan=skip_privacy_scan,
            privacy_assets=privacy_assets,
        )

        return result.artifacts
