# Removes the service's apps, which are what costs money. Runs inside Azure, so it works with no one at a computer.
param([object]$WebhookData)

$ErrorActionPreference = "Stop"
Connect-AzAccount -Identity | Out-Null

foreach ($type in "Microsoft.App/containerApps", "Microsoft.App/managedEnvironments") {
    Get-AzResource -ResourceGroupName "fruity" -ResourceType $type | ForEach-Object {
        Write-Output "Removing $($_.Name)"
        Remove-AzResource -ResourceId $_.ResourceId -Force | Out-Null
    }
}
