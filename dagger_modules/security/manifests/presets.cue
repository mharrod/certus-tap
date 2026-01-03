package assurance

presets: {
	light: #Profile & {
		name:        "light"
		description: "Ruff, Bandit, detect-secrets, Opengrep, Trivy, SBOM, privacy"
		tools: [
			tool_registry.ruff,
			tool_registry.bandit,
			tool_registry.detect_secrets,
			tool_registry.opengrep,
			tool_registry.trivy_fs,
			tool_registry.privacy,
			tool_registry.syft_sbom,
		]
		thresholds: {
			critical: 0
			high:     5
			medium:   50
		}
	}

	standard: #Profile & {
		name:        "standard"
		description: "Adds attestations and SBOM focus"
		tools: [
			tool_registry.ruff,
			tool_registry.bandit,
			tool_registry.detect_secrets,
			tool_registry.opengrep,
			tool_registry.trivy_fs,
			tool_registry.syft_sbom,
		]
		thresholds: {
			critical: 0
			high:     0
			medium:   25
		}
	}

	polyglot: #Profile & {
		name:        "polyglot"
		description: "Extended preset for repositories containing Python + JavaScript"
		tools: [
			tool_registry.ruff,
			tool_registry.bandit,
			tool_registry.detect_secrets,
			tool_registry.opengrep,
			tool_registry.trivy_fs,
			tool_registry.syft_sbom,
			{
				id:          "eslint-security"
				description: "ESLint security preset"
			},
			{
				id:          "retire-js"
				description: "Retire.js vulnerable dependency scan"
			},
		]
	}
}
