package assurance

tool_registry: {
	ruff: #Tool & {
		id:          "ruff"
		category:    "sast"
		description: "Python-focused lint/SAST"
		config: {
			command: ["ruff", "check", "."]
			output: "ruff.txt"
		}
	}

	bandit: #Tool & {
		id:          "bandit"
		category:    "sast"
		description: "Python security analyzer"
		config: {
			command: ["bandit", "-q", "-r", "."]
			format: "json"
			output: "bandit.json"
		}
	}

	detect_secrets: #Tool & {
		id:          "detect-secrets"
		category:    "secrets"
		description: "detect-secrets secret scanning"
		config: {
			command: ["detect-secrets", "scan", "--all-files"]
			output: "detect-secrets.json"
		}
	}

	opengrep: #Tool & {
		id:          "opengrep"
		category:    "sast"
		description: "Opengrep baseline rules"
		config: {
			configPath: "dagger_modules/security/config/semgrep-baseline.yml"
			output:     "opengrep.sarif.json"
		}
	}

	trivy_fs: #Tool & {
		id:          "trivy"
		category:    "container"
		description: "Trivy filesystem scan"
		config: {
			mode:   "fs"
			format: "sarif"
			output: "trivy.sarif.json"
		}
	}

	syft_sbom: #Tool & {
		id:          "sbom"
		category:    "sbom"
		description: "Syft SBOM generation"
		config: {
			formats: ["spdx-json", "cyclonedx-json"]
		}
	}

	privacy: #Tool & {
		id:          "privacy"
		category:    "privacy"
		description: "Sample privacy detector using assets/privacy-pack"
		config: {
			script: "security_module/scripts/privacy_scan.py"
		}
	}
}
