package assurance

#SeverityThreshold: {
	critical?: int & >=0
	high?:     int & >=0
	medium?:   int & >=0
	low?:      int & >=0
}

#Notification: {
	slack?: string
	webhooks?: [...string]
	email?: [...string]
}

#Tool: {
	id:           string
	description?: string
	category?:    string
	config?: [string]: _
}

#Profile: {
	name:         string
	description?: string
	tools: [...#Tool]
	thresholds?:    #SeverityThreshold
	requiresStack?: bool | *false
	notify?:        #Notification
	bundle?: {
		includePrivacy?:        bool | *true
		runtimeCeilingMinutes?: int
	}
}

#ComplianceTest: {
	name:         string
	description?: string
	evidence?: [...string]
	linkedProfile?: string
	threshold?:     #SeverityThreshold
}

#ComplianceControl: {
	framework: string
	controlId: string
	tests: [...#ComplianceTest]
}

#ComplianceOutcome: {
	name:         string
	description?: string
	controls: [...#ComplianceControl]
}

#Manifest: {
	product: string | *""
	version: string | *""
	owners: [...string]
	presets?: [...string]
	profiles: [...#Profile]
	compliance?: [...#ComplianceOutcome]
	annotations?: [string]: string
}

manifest: #Manifest
