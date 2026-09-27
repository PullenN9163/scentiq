param location string
param environmentName string
param webFqdn string
param applicationInsightsResourceId string
param commonTags object

var testLocations = [
  { Id: 'us-tx-sn1-azr' }
  { Id: 'us-il-ch1-azr' }
  { Id: 'us-ca-sjc-azr' }
]

var rootTestName = 'scentiq-web-root-${environmentName}'
var apiStatusTestName = 'scentiq-web-api-status-${environmentName}'

resource rootTest 'Microsoft.Insights/webtests@2022-06-15' = {
  name: rootTestName
  location: location
  kind: 'standard'
  tags: union(commonTags, {
    'hidden-link:${applicationInsightsResourceId}': 'Resource'
  })
  properties: {
    Description: 'ScentIQ public root availability. Runbook: docs/runbooks/azure-deployment.md#monitoring-alerts'
    Enabled: true
    Frequency: 300
    Kind: 'standard'
    Locations: testLocations
    Name: rootTestName
    Request: {
      FollowRedirects: false
      Headers: []
      HttpVerb: 'GET'
      ParseDependentRequests: false
      RequestUrl: 'https://${webFqdn}/'
    }
    RetryEnabled: true
    SyntheticMonitorId: rootTestName
    Timeout: 30
    ValidationRules: {
      ExpectedHttpStatusCode: 200
      SSLCertRemainingLifetimeCheck: 7
      SSLCheck: true
    }
  }
}

resource apiStatusTest 'Microsoft.Insights/webtests@2022-06-15' = {
  name: apiStatusTestName
  location: location
  kind: 'standard'
  tags: union(commonTags, {
    'hidden-link:${applicationInsightsResourceId}': 'Resource'
  })
  properties: {
    Description: 'ScentIQ frontend API-status availability. Runbook: docs/runbooks/azure-deployment.md#monitoring-alerts'
    Enabled: true
    Frequency: 300
    Kind: 'standard'
    Locations: testLocations
    Name: apiStatusTestName
    Request: {
      FollowRedirects: false
      Headers: []
      HttpVerb: 'GET'
      ParseDependentRequests: false
      RequestUrl: 'https://${webFqdn}/api/status'
    }
    RetryEnabled: true
    SyntheticMonitorId: apiStatusTestName
    Timeout: 30
    ValidationRules: {
      ExpectedHttpStatusCode: 200
      SSLCertRemainingLifetimeCheck: 7
      SSLCheck: true
    }
  }
}

output rootTestId string = rootTest.id
output apiStatusTestId string = apiStatusTest.id
