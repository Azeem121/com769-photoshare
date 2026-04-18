// main.bicep — Orchestrates all Azure resources for ScalableDemoApp
// Deploy: az deployment group create --resource-group <rg> --template-file main.bicep --parameters parameters/dev.parameters.json

targetScope = 'resourceGroup'

@description('Base name used for all resources (e.g. scalableapp)')
param appName string = 'scalableapp'

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Environment tag (dev/staging/prod)')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

// ── Modules ──────────────────────────────────────────────────────────────────

module storage 'modules/storage.bicep' = {
  name: 'storage-deploy'
  params: {
    appName: appName
    location: location
    environment: environment
  }
}

module cosmosdb 'modules/cosmosdb.bicep' = {
  name: 'cosmosdb-deploy'
  params: {
    appName: appName
    location: location
    environment: environment
  }
}

module functionapp 'modules/functionapp.bicep' = {
  name: 'functionapp-deploy'
  params: {
    appName: appName
    location: location
    environment: environment
    storageAccountName: storage.outputs.storageAccountName
    cosmosDbConnectionString: cosmosdb.outputs.connectionString
    blobConnectionString: storage.outputs.connectionString
  }
}

module staticwebapp 'modules/staticwebapp.bicep' = {
  name: 'staticwebapp-deploy'
  params: {
    appName: appName
    location: location
    environment: environment
  }
}

module cdn 'modules/cdn.bicep' = {
  name: 'cdn-deploy'
  params: {
    appName: appName
    location: location
    staticWebAppHostname: staticwebapp.outputs.defaultHostname
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────

output functionAppUrl string = functionapp.outputs.functionAppUrl
output staticWebAppUrl string = staticwebapp.outputs.defaultHostname
output cdnEndpointUrl string = cdn.outputs.cdnEndpointUrl
output storageAccountName string = storage.outputs.storageAccountName
output cosmosDbAccountName string = cosmosdb.outputs.accountName
