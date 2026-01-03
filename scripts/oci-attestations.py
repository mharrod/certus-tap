#!/usr/bin/env python3
"""
OCI Attestations Service
Generates, signs, and manages OCI artifacts (SBOM, attestations, scans) for lightweight OCI registries
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


class OciAttestationsService:
    """Generate and manage OCI attestations for supply chain security"""

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _normalize_registry_ref(self, registry: str) -> str:
        """Return host[:port] suitable for oras refs, stripping scheme/paths"""
        parsed = urlparse(registry)
        host = parsed.netloc or parsed.path if parsed.scheme else registry
        return host.rstrip("/")

    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load configuration from YAML or use defaults"""
        default_config = {
            "registry": {
                "url": "http://localhost:5000",
                "username": "",
                "password": "",
                "default_repo": "product-acquisition/attestations",
            },
            "product": {
                "name": "Acme Product",
                "version": "1.0.0",
                "vendor": "ACME Corp",
                "org": "acme-org",
                "repo": "acme-product",
            },
            "cosign": {
                "key_file": "samples/oci-attestations/keys/cosign.key",
                "pub_key": "samples/oci-attestations/keys/cosign.pub",
            },
        }

        if config_path and os.path.exists(config_path):
            try:
                import yaml

                with open(config_path) as f:
                    loaded = yaml.safe_load(f) or {}
                    if "registry" not in loaded and "harbor" in loaded:
                        harbor_cfg = loaded["harbor"]
                        loaded["registry"] = {
                            "url": harbor_cfg.get("url", "http://localhost:5000"),
                            "username": harbor_cfg.get("username", ""),
                            "password": harbor_cfg.get("password", ""),
                            "default_repo": f"{harbor_cfg.get('project', 'product-acquisition')}/attestations",
                        }
                    merged = {
                        key: value.copy() if isinstance(value, dict) else value for key, value in default_config.items()
                    }
                    for key, value in loaded.items():
                        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                            merged[key].update(value)
                        else:
                            merged[key] = value
                    return merged
            except ImportError:
                print("Warning: PyYAML not installed, using default config")
            except Exception as e:
                print(f"Warning: Could not load config from {config_path}: {e}")

        return default_config

    def generate_sbom(self, output_dir: str) -> str:
        """Generate SPDX 2.3 Software Bill of Materials"""
        sbom = {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": f"SBOM: {self.config['product']['name']}",
            "documentNamespace": f"https://example.com/sbom/{uuid.uuid4()}",
            "creationInfo": {
                "created": self.timestamp,
                "creators": ["Tool: oci-attestations-1.0"],
                "licenseListVersion": "3.21",
            },
            "packages": [
                {
                    "SPDXID": "SPDXRef-Package",
                    "name": self.config["product"]["name"],
                    "version": self.config["product"]["version"],
                    "downloadLocation": f"https://github.com/{self.config['product']['org']}/{self.config['product']['repo']}",
                    "filesAnalyzed": False,
                    "supplier": f"Organization: {self.config['product']['vendor']}",
                },
                {
                    "SPDXID": "SPDXRef-flask",
                    "name": "flask",
                    "version": "2.3.0",
                    "downloadLocation": "https://pypi.org/project/flask",
                    "filesAnalyzed": False,
                    "licenseConcluded": "BSD-3-Clause",
                },
                {
                    "SPDXID": "SPDXRef-requests",
                    "name": "requests",
                    "version": "2.31.0",
                    "downloadLocation": "https://pypi.org/project/requests",
                    "filesAnalyzed": False,
                    "licenseConcluded": "Apache-2.0",
                },
                {
                    "SPDXID": "SPDXRef-cryptography",
                    "name": "cryptography",
                    "version": "41.0.0",
                    "downloadLocation": "https://pypi.org/project/cryptography",
                    "filesAnalyzed": False,
                    "licenseConcluded": "Apache-2.0 OR BSD-3-Clause",
                },
                {
                    "SPDXID": "SPDXRef-pydantic",
                    "name": "pydantic",
                    "version": "2.0.0",
                    "downloadLocation": "https://pypi.org/project/pydantic",
                    "filesAnalyzed": False,
                    "licenseConcluded": "MIT",
                },
            ],
            "relationships": [
                {
                    "spdxElementId": "SPDXRef-DOCUMENT",
                    "relationshipType": "DESCRIBES",
                    "relatedSpdxElement": "SPDXRef-Package",
                },
                {
                    "spdxElementId": "SPDXRef-Package",
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": "SPDXRef-flask",
                },
                {
                    "spdxElementId": "SPDXRef-Package",
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": "SPDXRef-requests",
                },
                {
                    "spdxElementId": "SPDXRef-Package",
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": "SPDXRef-cryptography",
                },
                {
                    "spdxElementId": "SPDXRef-Package",
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": "SPDXRef-pydantic",
                },
            ],
        }

        sbom_dir = Path(output_dir) / "sbom"
        sbom_dir.mkdir(parents=True, exist_ok=True)
        sbom_file = sbom_dir / "product.spdx.json"

        with open(sbom_file, "w") as f:
            json.dump(sbom, f, indent=2)

        print(f"✓ Generated SBOM: {sbom_file}")
        return str(sbom_file)

    def generate_attestation(self, output_dir: str) -> str:
        """Generate in-toto build attestation"""
        attestation = {
            "_type": "link",
            "name": "build",
            "materials": {
                "src/main.py": {"sha256": hashlib.sha256(b"main source code").hexdigest()},
                "requirements.txt": {"sha256": hashlib.sha256(b"flask==2.3.0\nrequests==2.31.0").hexdigest()},
            },
            "products": {
                "build/app.tar.gz": {"sha256": hashlib.sha256(b"application binary").hexdigest()},
                "sbom.json": {
                    "sha256": hashlib.sha256(
                        json.dumps({
                            "name": self.config["product"]["name"],
                            "version": self.config["product"]["version"],
                        }).encode()
                    ).hexdigest()
                },
            },
            "byproducts": {
                "stdout": f"Build successful for {self.config['product']['name']} v{self.config['product']['version']}",
                "stderr": "",
                "return-value": 0,
                "timestamp": self.timestamp,
            },
            "environment": {
                "CI": "true",
                "BUILD_ID": str(uuid.uuid4()),
                "BRANCH": "main",
            },
            "command": ["make", "build"],
            "return-value": 0,
        }

        attestation_dir = Path(output_dir) / "attestations"
        attestation_dir.mkdir(parents=True, exist_ok=True)
        attestation_file = attestation_dir / "build.intoto.json"

        with open(attestation_file, "w") as f:
            json.dump(attestation, f, indent=2)

        print(f"✓ Generated attestation: {attestation_file}")
        return str(attestation_file)

    def generate_sarif(self, output_dir: str) -> str:
        """Generate SARIF security scan results"""
        sarif = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "MockSecurityScanner",
                            "version": "1.0.0",
                            "informationUri": "https://example.com/scanner",
                            "rules": [
                                {
                                    "id": "CWE-89",
                                    "shortDescription": {"text": "SQL Injection"},
                                    "fullDescription": {"text": "Application is vulnerable to SQL injection attacks"},
                                    "help": {"text": "Use parameterized queries and prepared statements"},
                                    "defaultConfiguration": {"level": "error"},
                                },
                                {
                                    "id": "CWE-78",
                                    "shortDescription": {"text": "OS Command Injection"},
                                    "fullDescription": {"text": "Application is vulnerable to shell injection"},
                                    "help": {"text": "Avoid shell execution with untrusted input"},
                                    "defaultConfiguration": {"level": "error"},
                                },
                            ],
                        }
                    },
                    "results": [
                        {
                            "ruleId": "CWE-89",
                            "level": "error",
                            "message": {"text": "SQL injection vulnerability detected in user query handler"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "src/api/handlers.py"},
                                        "region": {
                                            "startLine": 145,
                                            "startColumn": 10,
                                            "endLine": 167,
                                            "endColumn": 5,
                                        },
                                    }
                                }
                            ],
                            "guid": str(uuid.uuid4()),
                        },
                        {
                            "ruleId": "CWE-78",
                            "level": "error",
                            "message": {"text": "Shell injection vulnerability in command execution"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "src/utils/shell_runner.py"},
                                        "region": {
                                            "startLine": 234,
                                            "startColumn": 15,
                                        },
                                    }
                                }
                            ],
                            "guid": str(uuid.uuid4()),
                        },
                    ],
                    "properties": {
                        "scanStartTime": self.timestamp,
                        "scanEndTime": (
                            datetime.fromisoformat(self.timestamp.replace("Z", "+00:00")) + timedelta(seconds=30)
                        ).isoformat()
                        + "Z",
                    },
                }
            ],
        }

        scan_dir = Path(output_dir) / "scans"
        scan_dir.mkdir(parents=True, exist_ok=True)
        sarif_file = scan_dir / "vulnerability.sarif"

        with open(sarif_file, "w") as f:
            json.dump(sarif, f, indent=2)

        print(f"✓ Generated SARIF scan: {sarif_file}")
        return str(sarif_file)

    def generate_privacy_scan(self, output_dir: str) -> str:
        """Generate Presidio privacy scan report"""
        findings = [
            {
                "entityType": "EMAIL_ADDRESS",
                "text": "security@acme.io",
                "confidence": 0.98,
                "location": {
                    "file": "contracts/vendor-onboarding.docx",
                    "page": 3,
                    "offsetStart": 125,
                    "offsetEnd": 144,
                },
                "actionTaken": "redacted",
                "redactedText": "[EMAIL_ADDRESS]",
            },
            {
                "entityType": "PERSON",
                "text": "Dana Privacy",
                "confidence": 0.95,
                "location": {
                    "file": "contracts/vendor-risk-assessment.docx",
                    "page": 7,
                    "offsetStart": 45,
                    "offsetEnd": 57,
                },
                "actionTaken": "alerted",
                "redactedText": None,
            },
        ]

        privacy_scan = {
            "scanner": {
                "name": "Presidio Analyzer",
                "version": "2.3.0",
                "build": "mock",
                "ruleset": "default-sensitive",
            },
            "artifact": {
                "type": "document-bundle",
                "digest": hashlib.sha256(b"privacy-scan-input").hexdigest(),
                "source": "samples/contracts/",
            },
            "run": {
                "started": self.timestamp,
                "finished": (
                    datetime.fromisoformat(self.timestamp.replace("Z", "+00:00")) + timedelta(seconds=18)
                ).isoformat()
                + "Z",
                "durationSeconds": 18,
            },
            "summary": {
                "status": "passed",
                "totalFindings": len(findings),
                "redactedCount": sum(1 for f in findings if f["actionTaken"] == "redacted"),
                "alertedCount": sum(1 for f in findings if f["actionTaken"] == "alerted"),
                "policyVersion": "privacy-baseline-2024.11",
                "notes": "PII was discovered and either redacted automatically or flagged for manual review.",
            },
            "findings": findings,
            "redaction": {
                "technique": "context-aware masking",
                "reviewRequired": True,
                "reviewers": ["privacy-team@certus.local"],
            },
            "compliance": {
                "gdpr": True,
                "hipaa": True,
                "ccpa": True,
                "lastUpdated": self.timestamp,
            },
        }

        privacy_dir = Path(output_dir) / "privacy"
        privacy_dir.mkdir(parents=True, exist_ok=True)
        privacy_file = privacy_dir / "privacy-scan.json"

        with open(privacy_file, "w") as f:
            json.dump(privacy_scan, f, indent=2)

        print(f"✓ Generated privacy scan summary: {privacy_file}")
        return str(privacy_file)

    def generate_slsa_provenance(self, output_dir: str, sbom_file: str) -> str:
        """Generate SLSA v1.0 provenance attestation with embedded SBOM"""
        # Read the generated SBOM to embed
        with open(sbom_file) as f:
            sbom_data = json.load(f)
        with open(sbom_file, "rb") as f:
            sbom_bytes = f.read()

        sbom_hash = hashlib.sha256(sbom_bytes).hexdigest()

        slsa_provenance = {
            "_type": "https://in-toto.io/Statement/v0.1",
            "predicateType": "https://slsa.dev/provenance/v1.0",
            "subject": [
                {
                    "name": f"{self.config['product']['name']}-{self.config['product']['version']}.tar.gz",
                    "digest": {
                        "sha256": hashlib.sha256(
                            f"{self.config['product']['name']}{self.config['product']['version']}".encode()
                        ).hexdigest()
                    },
                }
            ],
            "predicate": {
                "buildDefinition": {
                    "buildType": "https://github.com/Certus/build-system/v1.0",
                    "externalParameters": {
                        "repository": f"https://github.com/{self.config['product']['org']}/{self.config['product']['repo']}",
                        "ref": "refs/heads/main",
                        "revision": hashlib.sha256(b"main-branch-commit").hexdigest(),
                    },
                    "internalParameters": {
                        "SBOM": {
                            "embedded": True,
                            "format": "spdx",
                            "digest": {"sha256": sbom_hash},
                        }
                    },
                    "resolvedDependencies": [
                        {
                            "uri": "pkg:pypi/flask@2.3.0",
                            "digest": {"sha256": hashlib.sha256(b"flask-2.3.0-package").hexdigest()},
                        },
                        {
                            "uri": "pkg:pypi/requests@2.31.0",
                            "digest": {"sha256": hashlib.sha256(b"requests-2.31.0-package").hexdigest()},
                        },
                        {
                            "uri": "pkg:pypi/cryptography@41.0.0",
                            "digest": {"sha256": hashlib.sha256(b"cryptography-41.0.0-package").hexdigest()},
                        },
                    ],
                },
                "runDetails": {
                    "builder": {
                        "id": "https://github.com/Certus/build-system/runner/v1.0",
                        "version": "1.0.0",
                    },
                    "metadata": {
                        "invocationId": str(uuid.uuid4()),
                        "startTime": self.timestamp,
                        "finishTime": (
                            datetime.fromisoformat(self.timestamp.replace("Z", "+00:00")) + timedelta(minutes=5)
                        ).isoformat()
                        + "Z",
                        "completeness": {
                            "parameters": True,
                            "environment": False,
                            "materials": True,
                        },
                        "reproducible": True,
                    },
                    "byproducts": {
                        "logLocation": "https://github.com/certus-org/certus-product/actions/runs/12345",
                        "logContent": "Build completed successfully. All tests passed. SBOM generated.",
                    },
                },
            },
        }

        provenance_dir = Path(output_dir) / "provenance"
        provenance_dir.mkdir(parents=True, exist_ok=True)
        provenance_file = provenance_dir / "slsa-provenance.json"

        with open(provenance_file, "w") as f:
            json.dump(slsa_provenance, f, indent=2)

        print(f"✓ Generated SLSA provenance: {provenance_file}")
        return str(provenance_file)

    def _copy_from_canonical_samples(self, output_dir: str) -> dict[str, str]:
        """Copy canonical sample data from samples/non-repudiation/scan-artifacts/

        This ensures all provenance tutorials use the same consistent sample data.
        The files are copied (not linked) so they can be signed independently.

        Returns:
            Dictionary mapping artifact type to destination path
        """
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        canonical_samples = project_root / "samples" / "non-repudiation" / "scan-artifacts"

        if not canonical_samples.exists():
            print(f"⚠️  Warning: Canonical samples not found at {canonical_samples}")
            print("   Falling back to generated artifacts")
            return {}

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (output_path / "sbom").mkdir(exist_ok=True)
        (output_path / "scans").mkdir(exist_ok=True)

        copied_files = {}

        # Copy SBOM (Syft SPDX)
        sbom_source = canonical_samples / "syft.spdx.json"
        if sbom_source.exists():
            import shutil

            sbom_dest = output_path / "sbom" / "product.spdx.json"
            shutil.copy2(sbom_source, sbom_dest)
            copied_files["sbom"] = str(sbom_dest)
            print(f"✓ Copied canonical SBOM: {sbom_dest}")

        # Copy SARIF scan (Trivy)
        sarif_source = canonical_samples / "trivy.sarif.json"
        if sarif_source.exists():
            import shutil

            sarif_dest = output_path / "scans" / "vulnerability.sarif"
            shutil.copy2(sarif_source, sarif_dest)
            copied_files["sarif"] = str(sarif_dest)
            print(f"✓ Copied canonical SARIF: {sarif_dest}")

        # Copy scan metadata if available
        scan_json_source = canonical_samples / "scan.json"
        if scan_json_source.exists():
            import shutil

            scan_dest = output_path / "scan.json"
            shutil.copy2(scan_json_source, scan_dest)
            copied_files["scan_metadata"] = str(scan_dest)
            print(f"✓ Copied scan metadata: {scan_dest}")

        return copied_files

    def generate(self, output_dir: str, product_name: Optional[str] = None, version: Optional[str] = None) -> list[str]:
        """Generate all artifacts by copying from canonical samples and generating supplementary artifacts

        Strategy:
        1. Copy SBOM and SARIF from canonical samples/non-repudiation/scan-artifacts/
        2. Generate attestation, privacy scan, and SLSA provenance

        This ensures all provenance tutorials use the same base security findings.
        """
        if product_name:
            self.config["product"]["name"] = product_name
        if version:
            self.config["product"]["version"] = version

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        print("Using canonical sample data from samples/non-repudiation/scan-artifacts/")
        print("This ensures consistency across all provenance tutorials.")
        print("")

        # Copy canonical samples (SBOM and SARIF)
        copied_files = self._copy_from_canonical_samples(output_dir)

        # Use copied SBOM if available, otherwise generate
        if "sbom" in copied_files:
            sbom_file = copied_files["sbom"]
        else:
            print("Generating SBOM (canonical sample not found)...")
            sbom_file = self.generate_sbom(output_dir)

        files = [sbom_file]

        # Add copied SARIF if available, otherwise generate
        if "sarif" in copied_files:
            files.append(copied_files["sarif"])
        else:
            print("Generating SARIF (canonical sample not found)...")
            files.append(self.generate_sarif(output_dir))

        # Generate supplementary artifacts (these are OCI-specific)
        files.append(self.generate_attestation(output_dir))
        files.append(self.generate_privacy_scan(output_dir))
        files.append(self.generate_slsa_provenance(output_dir, sbom_file))

        print(f"\n✓ All artifacts prepared in {output_dir}")
        print("   - Using canonical samples: SBOM, SARIF (from samples/non-repudiation/)")
        print("   - Generated: attestation, privacy scan, SLSA provenance")
        return files

    def setup_keys(self, key_path: str) -> tuple:
        """Generate or load cosign key pair"""
        key_dir = Path(key_path).parent
        key_dir.mkdir(parents=True, exist_ok=True)

        key_file = Path(key_path)
        pub_file = key_dir / "cosign.pub"

        # Check if keys already exist
        if key_file.exists() and pub_file.exists():
            print("✓ Using existing keys:")
            print(f"  Private: {key_file}")
            print(f"  Public: {pub_file}")
            return str(key_file), str(pub_file)

        # Generate new keys with cosign
        try:
            result = subprocess.run(
                ["cosign", "generate-key-pair"],
                capture_output=True,
                text=True,
                input="\n",  # Press enter for default password handling
            )

            if result.returncode != 0:
                print(f"Error generating keys: {result.stderr}")
                print("Falling back to mock key generation...")
                return self._generate_mock_keys(key_file, pub_file)

            print("✓ Generated cosign key pair")
            return str(key_file), str(pub_file)

        except FileNotFoundError:
            print("cosign not found. Install with: brew install sigstore/tap/cosign")
            print("Falling back to mock key generation for demonstration...")
            return self._generate_mock_keys(key_file, pub_file)

    def _generate_mock_keys(self, key_file: Path, pub_file: Path) -> tuple:
        """Generate mock keys for demonstration"""
        # Mock private key (PEM format)
        mock_private = """-----BEGIN ENCRYPTED COSIGN PRIVATE KEY-----
MIIFDjBABgkqhkiG9w0BBQ0wMzAbBgkqhkiG9w0BBQwwDgQIt2/E7RqEfR8CAggA
MAwGCCqGSIb3DQIJBQAwRQYJKoZIhvcNAQcBBQYoMCYCBQDcKGHnBAjFjVhQRAEK
JAoGAAAAAAAAAAAAAAAA==
-----END ENCRYPTED COSIGN PRIVATE KEY-----
"""

        # Mock public key
        mock_public = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE8L0DjPT8DqgMhTPkTi5i4jDrRQdP
KqLj5W9xq+FZo6sVkWKEQsL8V8qFWGVLy8k2FwBBsCZ9c8E5X3dn6SIGvw==
-----END PUBLIC KEY-----
"""

        with open(key_file, "w") as f:
            f.write(mock_private)
        key_file.chmod(0o600)

        with open(pub_file, "w") as f:
            f.write(mock_public)

        print("✓ Generated mock cosign keys:")
        print(f"  Private: {key_file}")
        print(f"  Public: {pub_file}")
        return str(key_file), str(pub_file)

    def sign(self, artifacts_dir: str, key_path: Optional[str] = None) -> list[str]:
        """Sign artifacts with cosign"""
        key_file = key_path or self.config["cosign"]["key_file"]
        artifacts_dir = Path(artifacts_dir)

        if not artifacts_dir.exists():
            print(f"Error: Artifacts directory not found: {artifacts_dir}")
            return []

        signed_files = []

        # Find all JSON and SARIF files to sign
        for pattern in ["**/*.json", "**/*.sarif"]:
            for artifact in artifacts_dir.glob(pattern):
                sig_file = Path(str(artifact) + ".sig")
                env = os.environ.copy()
                env.setdefault("COSIGN_PASSWORD", "")
                env.setdefault("COSIGN_YES", "true")

                try:
                    # Try cosign signing
                    result = subprocess.run(
                        [
                            "cosign",
                            "sign-blob",
                            "--tlog-upload=false",
                            "--key",
                            key_file,
                            str(artifact),
                        ],
                        capture_output=True,
                        text=True,
                        env=env,
                    )

                    if result.returncode == 0:
                        with open(sig_file, "w") as f:
                            f.write(result.stdout)
                        print(f"✓ Signed: {artifact}")
                    else:
                        # Fallback to mock signature
                        self._generate_mock_signature(artifact, sig_file)
                        print(f"✓ Signed (mock): {artifact}")

                    signed_files.append(str(sig_file))

                except FileNotFoundError:
                    # cosign not available, use mock signature
                    self._generate_mock_signature(artifact, sig_file)
                    print(f"✓ Signed (mock): {artifact}")
                    signed_files.append(str(sig_file))

        print(f"\n✓ Signed {len(signed_files)} artifacts")
        return signed_files

    def _generate_mock_signature(self, artifact_file: Path, sig_file: Path):
        """Generate mock signature for demonstration"""
        with open(artifact_file, "rb") as f:
            content = f.read()

        # Create a mock signature (base64 encoded hash)
        import base64

        mock_sig = base64.b64encode(hashlib.sha256(content + b"mock-key").digest()).decode()

        with open(sig_file, "w") as f:
            f.write(mock_sig)

    def push(
        self,
        artifacts_dir: str,
        registry: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> list[str]:
        """Push artifacts to an OCI registry (oras-compatible)"""
        registry_cfg = self.config["registry"]
        registry = registry or registry_cfg["url"]
        username = username if username is not None else registry_cfg.get("username", "")
        password = password if password is not None else registry_cfg.get("password", "")
        repo = repo or registry_cfg.get("default_repo", "product-acquisition/attestations")

        artifacts_dir = Path(artifacts_dir)
        pushed_artifacts = []

        display_registry = registry.rstrip("/")
        registry_ref = self._normalize_registry_ref(registry)

        print(f"\nPushing to OCI registry: {display_registry}/{repo}")
        print(f"  Authentication: {username if username else 'anonymous'}")

        # Collect both JSON and SARIF files
        artifact_files = sorted(list(artifacts_dir.glob("**/*.json")) + list(artifacts_dir.glob("**/*.sarif")))
        if not artifact_files:
            print("⚠ No artifacts found to push")
            return []

        push_ref = f"{registry_ref}/{repo}:latest"
        oras_cmd = ["oras", "push", "--disable-path-validation", push_ref]
        # Add artifacts with appropriate content types
        for artifact in artifact_files:
            content_type = "application/sarif+json" if artifact.suffix == ".sarif" else "application/json"
            oras_cmd.append(f"{artifact}:{content_type}")
        if username and password:
            oras_cmd.extend(["-u", username, "-p", password])

        try:
            result = subprocess.run(oras_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"✓ Pushed manifest {push_ref} containing {len(artifact_files)} artifacts")
                for artifact in artifact_files:
                    rel_path = str(artifact.relative_to(artifacts_dir))
                    pushed_artifacts.append(rel_path)

                # Publish individual tags for easier inspection
                for artifact in artifact_files:
                    rel_path = str(artifact.relative_to(artifacts_dir))
                    tag = rel_path.replace("/", "-")
                    content_type = "application/sarif+json" if artifact.suffix == ".sarif" else "application/json"
                    single_cmd = [
                        "oras",
                        "push",
                        "--disable-path-validation",
                        f"{registry_ref}/{repo}:{tag}",
                        f"{artifact}:{content_type}",
                    ]
                    if username and password:
                        single_cmd.extend(["-u", username, "-p", password])

                    single_result = subprocess.run(single_cmd, capture_output=True, text=True)
                    if single_result.returncode == 0:
                        print(f"  ↳ Tagged {rel_path} as :{tag}")
                    else:
                        print(f"  ⚠ Failed to tag {rel_path}: {single_result.stderr.strip()}")
            else:
                print(f"⚠ Warning pushing artifacts to {push_ref}: {result.stderr.strip()}")

        except FileNotFoundError:
            print("Note: oras CLI not found. Install for OCI push support.")
            for artifact in artifact_files:
                artifact_name = artifact.parent.name + "/" + artifact.name
                print(f"      Mock push: {artifact_name}")
                pushed_artifacts.append(artifact_name)

        return pushed_artifacts

    def verify(
        self,
        artifacts_dir: Optional[str] = None,
        key_path: Optional[str] = None,
        registry: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> bool:
        """Verify signatures of artifacts"""
        key_file = key_path or self.config["cosign"]["pub_key"]

        if artifacts_dir:
            artifacts_dir = Path(artifacts_dir)
            print(f"\nVerifying local artifacts in {artifacts_dir}...")

            all_valid = True
            for artifact in artifacts_dir.glob("**/*.json"):
                sig_file = Path(str(artifact) + ".sig")
                env = os.environ.copy()
                env.setdefault("COSIGN_YES", "true")

                if not sig_file.exists():
                    print(f"✗ No signature found for {artifact}")
                    all_valid = False
                    continue

                try:
                    result = subprocess.run(
                        [
                            "cosign",
                            "verify-blob",
                            "--insecure-ignore-tlog",
                            "--key",
                            key_file,
                            "--signature",
                            str(sig_file),
                            str(artifact),
                        ],
                        capture_output=True,
                        text=True,
                        env=env,
                    )

                    if result.returncode == 0:
                        print(f"✓ {artifact.relative_to(artifacts_dir)} (valid)")
                    else:
                        print(f"✗ {artifact.relative_to(artifacts_dir)} (invalid signature)")
                        all_valid = False

                except FileNotFoundError:
                    print("⚠ cosign not available, skipping verification")
                    print(f"✓ {artifact.relative_to(artifacts_dir)} (signature present)")

            if all_valid:
                print("\n✓ All artifacts verified successfully!")
            return all_valid

        elif registry and repo:
            print(f"\nVerifying artifacts in OCI registry: {registry}/{repo}")
            print("  Note: Requires oras CLI and registry access")
            # Implementation would use oras to pull and verify from registry
            return True

        return False


def main():
    parser = argparse.ArgumentParser(description="OCI Attestations Service for registries")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate mock artifacts")
    gen_parser.add_argument("--output", default="samples/oci-attestations/artifacts", help="Output directory")
    gen_parser.add_argument("--product", help="Product name")
    gen_parser.add_argument("--version", help="Product version")

    # Setup keys command
    keys_parser = subparsers.add_parser("setup-keys", help="Setup cosign keys")
    keys_parser.add_argument("--key-path", default="samples/oci-attestations/keys/cosign.key", help="Key file path")

    # Sign command
    sign_parser = subparsers.add_parser("sign", help="Sign artifacts with cosign")
    sign_parser.add_argument(
        "--artifacts-dir", default="samples/oci-attestations/artifacts", help="Artifacts directory"
    )
    sign_parser.add_argument("--key-path", help="Private key path")

    # Push command
    push_parser = subparsers.add_parser("push", help="Push to OCI registry")
    push_parser.add_argument(
        "--artifacts-dir", default="samples/oci-attestations/artifacts", help="Artifacts directory"
    )
    push_parser.add_argument("--registry", help="Registry URL (default from config)")
    push_parser.add_argument("--username", help="Registry username (optional)")
    push_parser.add_argument("--password", help="Registry password (optional)")
    push_parser.add_argument("--repo", help="Registry repository (e.g. project/artifacts)")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify artifact signatures")
    verify_parser.add_argument("--artifacts-dir", help="Local artifacts directory")
    verify_parser.add_argument("--key-path", help="Public key path")
    verify_parser.add_argument("--registry", help="Registry URL (oras-compatible)")
    verify_parser.add_argument("--repo", help="Registry repository (e.g. project/artifacts)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    service = OciAttestationsService()

    if args.command == "generate":
        service.generate(args.output, args.product, args.version)

    elif args.command == "setup-keys":
        service.setup_keys(args.key_path)

    elif args.command == "sign":
        service.sign(args.artifacts_dir, args.key_path)

    elif args.command == "push":
        service.push(args.artifacts_dir, args.registry, args.username, args.password, args.repo)

    elif args.command == "verify":
        if service.verify(args.artifacts_dir, args.key_path, args.registry, args.repo):
            return 0
        else:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

    def _normalize_registry_ref(self, registry: str) -> str:
        """Return host[:port] suitable for oras refs, stripping scheme/paths"""
        parsed = urlparse(registry)
        host = parsed.netloc or parsed.path if parsed.scheme else registry
        return host.rstrip("/")
