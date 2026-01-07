"""Run Certus Assurance security checks via Dagger.

This helper spins up a disposable Python container, installs the requested
security tools (OpenGrep, Bandit, Trivy), and executes them against the
current repository. Reports are exported to ``build/security-reports`` by
default so they can be reviewed locally or attached to CI artifacts.
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import shlex
import sys
from collections.abc import Sequence

import dagger

EXCLUDES = [
    ".git",
    ".venv",
    "dist",
    "site",
    "node_modules",
    "draft",
    "htmlcov",
    "__pycache__",
]


def _parse_extra(value: str | None) -> list[str]:
    return shlex.split(value) if value else []


def _tee_command(cmd: Sequence[str], output_file: str) -> list[str]:
    return [
        "sh",
        "-c",
        f"{shlex.join(cmd)} | tee {shlex.quote(output_file)}",
    ]


async def run_security_pipeline(args: argparse.Namespace) -> None:
    export_path = pathlib.Path(args.export_dir)

    async with dagger.Connection(dagger.Config(log_output=sys.stderr)) as client:
        src = client.host().directory(".", exclude=EXCLUDES)
        base = (
            client.container()
            .from_("python:3.11-slim")
            .with_env_variable("PIP_DISABLE_PIP_VERSION_CHECK", "1")
            .with_env_variable("PIP_NO_CACHE_DIR", "1")
            .with_workdir("/src")
            .with_mounted_directory("/src", src)
        )

        def run_cmd(container: dagger.Container, command: Sequence[str]) -> dagger.Container:
            return container.with_exec(list(command))

        tooling = base
        for command in (
            ["apt-get", "update"],
            ["apt-get", "install", "-y", "git", "wget", "curl", "apt-transport-https", "gnupg", "lsb-release"],
        ):
            tooling = run_cmd(tooling, command)

        tooling = run_cmd(tooling, ["pip", "install", "--no-cache-dir", "opengrep", "bandit"])

        tooling = run_cmd(
            tooling,
            [
                "sh",
                "-c",
                "wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key "
                "| gpg --dearmor -o /usr/share/keyrings/trivy.gpg",
            ],
        )
        tooling = run_cmd(
            tooling,
            [
                "sh",
                "-c",
                'echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] '
                'https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" '
                "> /etc/apt/sources.list.d/trivy.list",
            ],
        )
        tooling = run_cmd(tooling, ["apt-get", "update"])
        tooling = run_cmd(tooling, ["apt-get", "install", "-y", "trivy"])
        tooling = run_cmd(tooling, ["mkdir", "-p", "/tmp/security-reports"])

        security_dir = "/tmp/security-reports"

        opengrep_cmd = ["opengrep", "scan", ".", *_parse_extra(args.opengrep_args)]
        bandit_cmd = [
            "bandit",
            "-q",
            "-r",
            ".",
            "-f",
            "json",
            "-o",
            f"{security_dir}/bandit.json",
            *_parse_extra(args.bandit_args),
        ]
        trivy_cmd = [
            "trivy",
            "fs",
            "--scanners",
            "vuln,secret,config",
            "--format",
            "json",
            "--output",
            f"{security_dir}/trivy.json",
            ".",
            *_parse_extra(args.trivy_args),
        ]

        opengrep_output = await run_cmd(tooling, _tee_command(opengrep_cmd, f"{security_dir}/opengrep.txt")).stdout()
        print("\n[opengrep]\n", opengrep_output.strip())

        await run_cmd(tooling, bandit_cmd).exit_code()
        await run_cmd(tooling, trivy_cmd).exit_code()

        reports = tooling.directory(security_dir)
        export_target = str(export_path)
        print(f"\nExporting reports to {export_target} ...")
        await reports.export(export_target)
        print("Security scans complete.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Certus Assurance Dagger security checks.")
    parser.add_argument(
        "--export-dir",
        default="build/security-reports",
        help="Directory to export scan outputs (default: %(default)s)",
    )
    parser.add_argument(
        "--opengrep-args",
        default="",
        help="Additional arguments forwarded to opengrep (quoted string).",
    )
    parser.add_argument(
        "--bandit-args",
        default="",
        help="Additional arguments forwarded to bandit.",
    )
    parser.add_argument(
        "--trivy-args",
        default="",
        help="Additional arguments forwarded to trivy.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run_security_pipeline(args))


if __name__ == "__main__":
    main()
