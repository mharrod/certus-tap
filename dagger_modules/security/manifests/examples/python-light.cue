package examples_python_light

import manifests "github.com/certus/assurance-manifests:assurance"

manifest: manifests.#Manifest & {
	product: "certus-tap"
	version: "1.0.0"
	owners: ["security@certus.dev"]
	presets: ["light"]

	profiles: [
		manifests.presets.light & {
			notify: {
				slack: "#security-alerts"
			}
		},
	]

	compliance: [{
		name:        "HIPAA Privacy Baseline"
		description: "Maps SAST/SCA evidence to HIPAA safeguards"
		controls: [{
			framework: "HIPAA"
			controlId: "164.308(a)(1)(ii)(A)"
			tests: [{
				name: "SAST + SCA baseline"
				evidence: ["bandit.json", "trivy.sarif.json"]
				linkedProfile: manifests.presets.light.name
				threshold: {
					critical: 0
					high:     5
				}
			}]
		}]
	}]
}
