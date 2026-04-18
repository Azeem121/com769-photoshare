// staticwebapp.bicep — Azure Static Web Apps (free tier)

param appName string
param location string
param environment string

var swaName = 'swa-${appName}-${environment}'

resource staticWebApp 'Microsoft.Web/staticSites@2023-01-01' = {
  name: swaName
  // SWA free tier is only available in specific regions
  location: 'eastus2'
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    stagingEnvironmentPolicy: 'Enabled'
    allowConfigFileUpdates: true
    buildProperties: {
      appLocation: 'frontend'
      apiLocation: ''
      outputLocation: ''
    }
  }
  tags: {
    environment: environment
    project: appName
  }
}

output defaultHostname string = staticWebApp.properties.defaultHostname
output swaName string = staticWebApp.name
output deploymentToken string = staticWebApp.listSecrets().properties.apiKey
