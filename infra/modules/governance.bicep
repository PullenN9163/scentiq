param environmentName string
param alertEmails array
param budgetAmount int = 50
param commonTags object

var budgetName = 'scentiq-budget-${environmentName}-monthly'

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'scentiq-ag-${environmentName}-eus'
  location: 'global'
  tags: commonTags
  properties: {
    groupShortName: 'scentiq'
    enabled: true
    emailReceivers: [
      for (emailAddress, index) in alertEmails: {
        name: 'operations-${index + 1}'
        emailAddress: emailAddress
        useCommonAlertSchema: true
      }
    ]
  }
}

resource budget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: budgetName
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: '2026-08-01T00:00:00Z'
      endDate: '2036-08-01T00:00:00Z'
    }
    notifications: {
      actual_50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        thresholdType: 'Actual'
        locale: 'en-us'
        contactEmails: []
        contactGroups: [
          actionGroup.id
        ]
      }
      actual_80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        locale: 'en-us'
        contactEmails: []
        contactGroups: [
          actionGroup.id
        ]
      }
      actual_100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        locale: 'en-us'
        contactEmails: []
        contactGroups: [
          actionGroup.id
        ]
      }
      actual_120: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 120
        thresholdType: 'Actual'
        locale: 'en-us'
        contactEmails: []
        contactGroups: [
          actionGroup.id
        ]
      }
      forecast_80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Forecasted'
        locale: 'en-us'
        contactEmails: []
        contactGroups: [
          actionGroup.id
        ]
      }
    }
  }
}

output actionGroupId string = actionGroup.id
output budgetName string = budget.name
