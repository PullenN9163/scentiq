targetScope = 'resourceGroup'

param commonTags object

resource tags 'Microsoft.Resources/tags@2021-04-01' = {
  name: 'default'
  properties: {
    tags: union(resourceGroup().tags, commonTags)
  }
}
