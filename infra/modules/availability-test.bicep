param location string
param environmentName string
param webFqdn string
param applicationInsightsResourceId string
param commonTags object
@allowed([900])
param frequencySeconds int = 900
@allowed(['us-tx-sn1-azr'])
param locationId string = 'us-tx-sn1-azr'

var testLocations = [ { Id: locationId } ]

var apiStatusTestName = 'scentiq-web-api-status-${environmentName}'

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
    Frequency: frequencySeconds
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

output apiStatusTestId string = apiStatusTest.id
