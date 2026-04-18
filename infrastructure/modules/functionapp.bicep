// functionapp.bicep — Azure Function App (consumption plan, Python 3.11)

param appName string
param location string
param environment string
param storageAccountName string
param cosmosDbConnectionString string
param blobConnectionString string

var funcAppName = 'func-${appName}-${environment}'
var hostingPlanName = 'plan-${appName}-${environment}'
var appInsightsName = 'appi-${appName}-${environment}'

// Application Insights (free tier: 5 GB/month ingestion)
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    RetentionInDays: 30
  }
  tags: {
    environment: environment
    project: appName
  }
}

// Consumption (serverless) hosting plan — free
resource hostingPlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: hostingPlanName
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true  // Required for Linux
  }
  tags: {
    environment: environment
    project: appName
  }
}

// Reference existing storage account for AzureWebJobsStorage
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: funcAppName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: hostingPlan.id
    reserved: true
    siteConfig: {
      pythonVersion: '3.11'
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(funcAppName)
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'COSMOS_DB_CONNECTION_STRING'
          value: cosmosDbConnectionString
        }
        {
          name: 'COSMOS_DB_DATABASE_NAME'
          value: 'photoshare'
        }
        {
          name: 'BLOB_STORAGE_CONNECTION_STRING'
          value: blobConnectionString
        }
        {
          name: 'BLOB_CONTAINER_NAME'
          value: 'photos'
        }
        {
          name: 'JWT_SECRET'
          value: 'REPLACE_WITH_STRONG_SECRET_IN_KEYVAULT'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
      ]
      cors: {
        allowedOrigins: ['*']
        supportCredentials: false
      }
    }
    httpsOnly: true
  }
  tags: {
    environment: environment
    project: appName
  }
}

output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output functionAppName string = functionApp.name
