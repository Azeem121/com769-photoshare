// cdn.bicep — Azure CDN profile + endpoint pointing at Static Web App
// Uses Microsoft CDN (free tier: 15 GB/month for 12 months)

param appName string
param location string
param staticWebAppHostname string

var cdnProfileName = 'cdn-${appName}'
var cdnEndpointName = 'cdnep-${appName}'

resource cdnProfile 'Microsoft.Cdn/profiles@2023-05-01' = {
  name: cdnProfileName
  location: 'global'
  sku: {
    name: 'Standard_Microsoft'  // Free for first 12 months (15 GB/month)
  }
  tags: {
    project: appName
  }
}

resource cdnEndpoint 'Microsoft.Cdn/profiles/endpoints@2023-05-01' = {
  parent: cdnProfile
  name: cdnEndpointName
  location: 'global'
  properties: {
    originHostHeader: staticWebAppHostname
    isHttpAllowed: false
    isHttpsAllowed: true
    queryStringCachingBehavior: 'IgnoreQueryString'
    origins: [
      {
        name: 'static-web-app-origin'
        properties: {
          hostName: staticWebAppHostname
          httpsPort: 443
          originHostHeader: staticWebAppHostname
        }
      }
    ]
    deliveryPolicy: {
      rules: [
        {
          name: 'CacheStaticAssets'
          order: 1
          conditions: [
            {
              name: 'UrlFileExtension'
              parameters: {
                typeName: 'DeliveryRuleUrlFileExtensionMatchConditionParameters'
                operator: 'Equal'
                negateCondition: false
                matchValues: ['jpg', 'jpeg', 'png', 'gif', 'webp', 'css', 'js', 'woff2']
              }
            }
          ]
          actions: [
            {
              name: 'CacheExpiration'
              parameters: {
                typeName: 'DeliveryRuleCacheExpirationActionParameters'
                cacheBehavior: 'Override'
                cacheType: 'All'
                cacheDuration: '7.00:00:00'  // 7-day cache for static assets
              }
            }
          ]
        }
      ]
    }
  }
}

output cdnEndpointUrl string = 'https://${cdnEndpoint.properties.hostName}'
output cdnProfileName string = cdnProfile.name
