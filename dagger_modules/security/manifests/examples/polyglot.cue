package examples_polyglot

import manifests "github.com/certus/assurance-manifests:assurance"

manifest: manifests.#Manifest & {
	product: "customer-portal"
	version: "2.3.0"
	owners: ["platform@certus.dev", "security@certus.dev"]
	presets: [
		"light",
		"polyglot",
	]

	profiles: [
		manifests.presets.polyglot & {
			name: "polyglot"
			notify: {
				slack: "#platform-alerts"
				webhooks: ["https://hooks.slack.com/services/example"]
			}
		},
	]
}
