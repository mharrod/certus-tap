"""CLI wrapper for running security profiles via runtime abstraction."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Literal

from security_module.constants import DEFAULT_EXPORT_DIR
from security_module.runtime import DaggerRuntime, LocalRuntime, RuntimeResult
from security_module.scanner import SecurityScanner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Certus security profiles via CLI or Dagger.")
    parser.add_argument(
        "--export-dir",
        default=str(DEFAULT_EXPORT_DIR),
        help="Local directory to export artifacts (default: %(default)s)",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace path to mount inside the container (default: current directory)",
    )
    parser.add_argument(
        "--bundle-id",
        default=None,
        help="Optional bundle identifier (default: timestamp + git short SHA)",
    )
    parser.add_argument(
        "--profile",
        default="standard",
        help="Which profile to run (default: %(default)s). Built-in: smoke, fast, medium, standard, full, light, heavy, javascript, attestation-test. Custom names allowed when using --manifest.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Path to exported assurance manifest JSON (optional)",
    )
    parser.add_argument(
        "--runtime",
        choices=["dagger", "local"],
        default="dagger",
        help="Execution runtime (default: dagger)",
    )
    parser.add_argument(
        "--skip-privacy-scan",
        action="store_true",
        help="Skip privacy scan even if profile requests it",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum execution time in seconds (default: no timeout for Dagger operations)",
    )
    return parser


def _build_runtime(runtime_name: Literal["dagger", "local"], timeout: float | None = None) -> DaggerRuntime | LocalRuntime:
    if runtime_name == "local":
        return LocalRuntime()
    return DaggerRuntime(timeout=timeout)


async def _run_cli(args: argparse.Namespace) -> RuntimeResult:
    runtime = _build_runtime(args.runtime, timeout=args.timeout)
    scanner = SecurityScanner(runtime)
    return await scanner.run(
        profile=args.profile,
        workspace=args.workspace,
        export_dir=args.export_dir,
        bundle_id=args.bundle_id,
        manifest_path=args.manifest,
        skip_privacy_scan=args.skip_privacy_scan,
    )


def _update_latest_symlink(target_root: Path, result: RuntimeResult) -> None:
    bundle_path = Path(result.artifacts)
    latest_link = target_root / "latest"

    # Use relative path for symlink (just the directory name, not full path)
    try:
        relative_target = bundle_path.relative_to(target_root)
    except ValueError:
        # If bundle_path is not under target_root, use the directory name
        relative_target = bundle_path.name

    if latest_link.exists() or latest_link.is_symlink():
        try:
            if latest_link.is_dir() and not latest_link.is_symlink():
                import shutil

                shutil.rmtree(latest_link)
            else:
                latest_link.unlink()
        except OSError as exc:
            print(f"Error removing old 'latest' link: {exc}")
            return
    try:
        latest_link.symlink_to(relative_target, target_is_directory=True)
    except OSError:
        try:
            latest_link.write_text(str(bundle_path))
        except OSError as exc:
            print(f"Error writing to 'latest': {exc}")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = asyncio.run(_run_cli(args))
    export_root = Path(args.export_dir).expanduser().resolve()
    export_root.mkdir(parents=True, exist_ok=True)
    _update_latest_symlink(export_root, result)

    # Display policy results
    print(f"\n✓ Scan completed: {result.bundle_id}")
    print(f"  Artifacts: {result.artifacts}")

    if result.policy_passed is not None:
        if result.policy_passed:
            print("  Policy: ✓ PASSED")
        else:
            print("  Policy: ✗ FAILED")
            if result.policy_violations:
                for violation in result.policy_violations:
                    print(f"    - {violation}")
            print(f"\n  Review artifacts at: {result.artifacts}/policy-result.json")
            print("  Note: Artifacts were exported for review. Calling pipeline should decide on blocking actions.")


if __name__ == "__main__":
    main()
