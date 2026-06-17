<#
Exports hourly RegionEnergyMainDevices rows from ENTBUS.

Example:
  powershell -ExecutionPolicy Bypass -File .\scripts\export_entbus_region_energy_hourly.ps1

Specific date/region:
  powershell -ExecutionPolicy Bypass -File .\scripts\export_entbus_region_energy_hourly.ps1 -Date 2026-06-16 -RegionId 1
#>

[CmdletBinding()]
param(
    [string]$BaseUrl = "http://192.168.0.11",
    [int]$UserId = 8,
    [int]$RegionId = 1,
    [datetime]$Date = (Get-Date).Date.AddDays(-1),
    [string]$OutputPath
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function ConvertTo-SoapRows {
    param($Data)

    if ($null -eq $Data) {
        return @()
    }

    $items = @($Data)
    if ($items.Count -eq 0) {
        return @()
    }

    $first = $items[0]
    if ($null -ne $first -and ($first.PSObject.Properties.Name -contains "Key")) {
        $row = [ordered]@{}
        foreach ($kv in $items) {
            if ($null -ne $kv -and ($kv.PSObject.Properties.Name -contains "Key")) {
                $row[[string]$kv.Key] = $kv.Value
            }
        }
        return @([pscustomobject]$row)
    }

    $rows = foreach ($item in $items) {
        if ($item -is [Array]) {
            $row = [ordered]@{}
            foreach ($kv in $item) {
                if ($null -ne $kv -and ($kv.PSObject.Properties.Name -contains "Key")) {
                    $row[[string]$kv.Key] = $kv.Value
                }
            }
            if ($row.Count -gt 0) {
                [pscustomobject]$row
            }
        }
        elseif ($null -ne $item -and ($item.PSObject.Properties.Name -contains "Key")) {
            [pscustomobject]@{ ([string]$item.Key) = $item.Value }
        }
        else {
            $item
        }
    }

    return @($rows)
}

function ConvertTo-EntbusDecimal {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [System.Byte] -or
        $Value -is [System.SByte] -or
        $Value -is [System.Int16] -or
        $Value -is [System.UInt16] -or
        $Value -is [System.Int32] -or
        $Value -is [System.UInt32] -or
        $Value -is [System.Int64] -or
        $Value -is [System.UInt64] -or
        $Value -is [System.Single] -or
        $Value -is [System.Double] -or
        $Value -is [System.Decimal]) {
        $numericText = [Convert]::ToString($Value, [Globalization.CultureInfo]::InvariantCulture)
        return [decimal]::Parse($numericText, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture)
    }

    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    if ($text.Contains(",") -and -not $text.Contains(".")) {
        $text = $text.Replace(",", ".")
    }

    return [decimal]::Parse($text, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture)
}

function Format-InvariantDecimal {
    param($Value)

    if ($null -eq $Value) {
        return ""
    }

    return ([decimal]$Value).ToString("0.###############", [Globalization.CultureInfo]::InvariantCulture)
}

function Get-PropertyValue {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($Object.PSObject.Properties.Name -contains $Name) {
        return $Object.$Name
    }

    return $null
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $dataDir = Join-Path (Get-Location) "data"
    $OutputPath = Join-Path $dataDir ("entbus_region_energy_hourly_{0:yyyyMMdd}.csv" -f $Date)
}

$BaseUrl = $BaseUrl.TrimEnd("/")
$wsdlUrl = "$BaseUrl/services/ReportsService.svc?wsdl"
$dayStart = $Date.Date
$dayEnd = $Date.Date.AddDays(1)

Write-Host "Connecting to $wsdlUrl"
$service = New-WebServiceProxy -Uri $wsdlUrl -Namespace EntbusRegionEnergyHourly -Class ReportsServiceProxy

Write-Host ("Exporting RegionEnergyMainDevices UserId={0}, RegionId={1}, Date={2:yyyy-MM-dd}" -f $UserId, $RegionId, $dayStart)

$numericFields = @("ImWh", "ExWh", "IndVarh", "CapVarh", "IndPenalty", "CapPenalty")
$exportRows = New-Object System.Collections.Generic.List[object]
$failures = New-Object System.Collections.Generic.List[object]

for ($hourStart = $dayStart; $hourStart -lt $dayEnd; $hourStart = $hourStart.AddHours(1)) {
    $hourEnd = $hourStart.AddHours(1)

    try {
        $rows = @(ConvertTo-SoapRows (
            $service.RegionEnergyMainDevices(
                $UserId,
                $true,
                $RegionId,
                $true,
                $hourStart,
                $true,
                $hourEnd,
                $true
            )
        ))

        foreach ($row in $rows) {
            $parsed = @{}
            foreach ($field in $numericFields) {
                $parsed[$field] = Format-InvariantDecimal (ConvertTo-EntbusDecimal (Get-PropertyValue $row $field))
            }

            $exportRows.Add([pscustomobject]@{
                Date = $hourStart.ToString("yyyy-MM-dd")
                HourStart = $hourStart.ToString("yyyy-MM-dd HH:mm:ss")
                HourEnd = $hourEnd.ToString("yyyy-MM-dd HH:mm:ss")
                UserId = $UserId
                RegionId = $RegionId
                Name = [string](Get-PropertyValue $row "Name")
                ImWh = $parsed["ImWh"]
                ExWh = $parsed["ExWh"]
                IndVarh = $parsed["IndVarh"]
                CapVarh = $parsed["CapVarh"]
                IndPenalty = $parsed["IndPenalty"]
                CapPenalty = $parsed["CapPenalty"]
            })
        }
    }
    catch {
        $failures.Add([pscustomobject]@{
            HourStart = $hourStart.ToString("yyyy-MM-dd HH:mm:ss")
            HourEnd = $hourEnd.ToString("yyyy-MM-dd HH:mm:ss")
            Error = $_.Exception.Message
        })
    }
}

$outputDirectory = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

$exportRows |
    Sort-Object HourStart, Name |
    Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding UTF8

Write-Host "Wrote $($exportRows.Count) rows to $OutputPath"

if ($failures.Count -gt 0) {
    Write-Warning "Some hourly calls failed:"
    $failures | Format-Table -AutoSize
}
