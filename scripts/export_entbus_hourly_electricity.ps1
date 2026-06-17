<# 
Exports yesterday's hourly imported electricity for each ENTBUS machine.

Example:
  powershell -ExecutionPolicy Bypass -File .\scripts\export_entbus_hourly_electricity.ps1

Specific date:
  powershell -ExecutionPolicy Bypass -File .\scripts\export_entbus_hourly_electricity.ps1 -Date 2026-06-16
#>

[CmdletBinding()]
param(
    [string]$BaseUrl = "http://192.168.0.11",
    [int]$UserId = 8,
    [datetime]$Date = (Get-Date).Date.AddDays(-1),
    [string[]]$RegionIds,
    [string[]]$DeviceIds,
    [string]$OutputPath,
    [switch]$IncludeEmptyMachines
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

    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    $styles = [Globalization.NumberStyles]::Float -bor [Globalization.NumberStyles]::AllowThousands
    foreach ($cultureName in @("tr-TR", "en-US", "")) {
        try {
            $culture = if ($cultureName -eq "") {
                [Globalization.CultureInfo]::InvariantCulture
            }
            else {
                [Globalization.CultureInfo]::GetCultureInfo($cultureName)
            }

            return [decimal]::Parse($text, $styles, $culture)
        }
        catch {
            # Try the next culture.
        }
    }

    throw "Cannot parse numeric value '$text'."
}

function Format-InvariantDecimal {
    param($Value)

    if ($null -eq $Value) {
        return ""
    }

    return ([decimal]$Value).ToString("0.##########", [Globalization.CultureInfo]::InvariantCulture)
}

function ConvertTo-EntbusDate {
    param([string]$Value)

    foreach ($cultureName in @("tr-TR", "en-US", "")) {
        try {
            $culture = if ($cultureName -eq "") {
                [Globalization.CultureInfo]::InvariantCulture
            }
            else {
                [Globalization.CultureInfo]::GetCultureInfo($cultureName)
            }

            return [datetime]::Parse($Value, $culture)
        }
        catch {
            # Try the next culture.
        }
    }

    throw "Cannot parse date value '$Value'."
}

function ConvertTo-IdList {
    param(
        [string[]]$Values,
        [string]$ParameterName
    )

    if ($null -eq $Values -or $Values.Count -eq 0) {
        return @()
    }

    $ids = foreach ($value in $Values) {
        ([string]$value) -split "[,;\s]+" |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            ForEach-Object {
                $parsed = 0
                if (-not [int]::TryParse($_, [Globalization.NumberStyles]::Integer, [Globalization.CultureInfo]::InvariantCulture, [ref]$parsed)) {
                    throw "Invalid $ParameterName value '$value'. Use numeric IDs such as 1,2,3."
                }
                $parsed
            }
    }

    return @($ids)
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
    $OutputPath = Join-Path $dataDir ("entbus_hourly_electricity_{0:yyyyMMdd}.csv" -f $Date)
}

$BaseUrl = $BaseUrl.TrimEnd("/")
$wsdlUrl = "$BaseUrl/services/ReportsService.svc?wsdl"
$start = $Date.Date
$end = $Date.Date.AddDays(1)
$regionIdFilter = @(ConvertTo-IdList $RegionIds "RegionIds")
$deviceIdFilter = @(ConvertTo-IdList $DeviceIds "DeviceIds")

Write-Host "Connecting to $wsdlUrl"
$service = New-WebServiceProxy -Uri $wsdlUrl -Namespace EntbusHourly -Class ReportsServiceProxy

$regions = @(ConvertTo-SoapRows ($service.GetRegionsForComboBox($UserId, $true)))
if ($regionIdFilter.Count -gt 0) {
    $regionIdSet = @{}
    foreach ($id in $regionIdFilter) {
        $regionIdSet[[int]$id] = $true
    }
    $regions = @($regions | Where-Object { $regionIdSet.ContainsKey([int]$_.ID) })
}

if ($regions.Count -eq 0) {
    throw "No ENTBUS regions found for UserId $UserId."
}

$devicesById = [ordered]@{}
foreach ($region in $regions) {
    $regionId = [int]$region.ID
    $regionName = [string]$region.Name
    $regionDevices = @(ConvertTo-SoapRows ($service.GetDevicesbyRegionIDForComboBox($regionId, $true, $UserId, $true)))

    foreach ($device in $regionDevices) {
        $deviceId = [int]$device.ID
        $deviceKey = [string]$deviceId
        if (-not $devicesById.Contains($deviceKey)) {
            $devicesById[$deviceKey] = [pscustomobject]@{
                DeviceId = $deviceId
                DeviceName = [string]$device.Name
                RegionId = $regionId
                RegionName = $regionName
            }
        }
    }
}

$devices = @($devicesById.Values)
if ($deviceIdFilter.Count -gt 0) {
    $deviceIdSet = @{}
    foreach ($id in $deviceIdFilter) {
        $deviceIdSet[[int]$id] = $true
    }
    $devices = @($devices | Where-Object { $deviceIdSet.ContainsKey([int]$_.DeviceId) })
}

if ($devices.Count -eq 0) {
    throw "No ENTBUS devices found for the selected filters."
}

Write-Host ("Exporting {0:yyyy-MM-dd} hourly electricity for {1} machines..." -f $start, $devices.Count)

$exportRows = New-Object System.Collections.Generic.List[object]
$failures = New-Object System.Collections.Generic.List[object]
$emptyMachines = New-Object System.Collections.Generic.List[object]

foreach ($device in $devices) {
    try {
        $reportRows = @(ConvertTo-SoapRows (
            $service.ActiveConsuptionProfileReport(
                [string]$device.DeviceId,
                $start,
                $true,
                $end,
                $true
            )
        ))

        if ($reportRows.Count -eq 0) {
            $emptyMachines.Add([pscustomobject]@{
                DeviceId = $device.DeviceId
                DeviceName = $device.DeviceName
            })

            if ($IncludeEmptyMachines) {
                $exportRows.Add([pscustomobject]@{
                    Date = $start.ToString("yyyy-MM-dd")
                    HourStart = ""
                    DeviceId = $device.DeviceId
                    DeviceName = $device.DeviceName
                    RegionId = $device.RegionId
                    RegionName = $device.RegionName
                    ReportName = ""
                    ImWhRaw = ""
                    ImportWh = ""
                    ImportKWh = ""
                })
            }
            continue
        }

        foreach ($reportRow in $reportRows) {
            $dateText = [string](Get-PropertyValue $reportRow "Date")
            if ([string]::IsNullOrWhiteSpace($dateText)) {
                $failures.Add([pscustomobject]@{
                    DeviceId = $device.DeviceId
                    DeviceName = $device.DeviceName
                    Error = "Skipped report row without Date."
                })
                continue
            }

            try {
                $timestamp = ConvertTo-EntbusDate $dateText
            }
            catch {
                $failures.Add([pscustomobject]@{
                    DeviceId = $device.DeviceId
                    DeviceName = $device.DeviceName
                    Error = "Skipped report row with invalid Date '$dateText'."
                })
                continue
            }

            $rawImWh = Get-PropertyValue $reportRow "ImWh"
            try {
                $importWh = ConvertTo-EntbusDecimal $rawImWh
            }
            catch {
                $failures.Add([pscustomobject]@{
                    DeviceId = $device.DeviceId
                    DeviceName = $device.DeviceName
                    Error = "Skipped report row with invalid ImWh '$rawImWh'."
                })
                continue
            }
            $importKWh = if ($null -eq $importWh) { $null } else { $importWh / 1000 }

            $exportRows.Add([pscustomobject]@{
                Date = $timestamp.ToString("yyyy-MM-dd")
                HourStart = $timestamp.ToString("yyyy-MM-dd HH:mm:ss")
                DeviceId = $device.DeviceId
                DeviceName = $device.DeviceName
                RegionId = $device.RegionId
                RegionName = $device.RegionName
                ReportName = [string](Get-PropertyValue $reportRow "Name")
                ImWhRaw = [string]$rawImWh
                ImportWh = Format-InvariantDecimal $importWh
                ImportKWh = Format-InvariantDecimal $importKWh
            })
        }
    }
    catch {
        $failures.Add([pscustomobject]@{
            DeviceId = $device.DeviceId
            DeviceName = $device.DeviceName
            Error = $_.Exception.Message
        })
    }
}

$outputDirectory = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

$exportRows |
    Sort-Object DeviceId, HourStart |
    Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding UTF8

Write-Host "Wrote $($exportRows.Count) rows to $OutputPath"

if ($emptyMachines.Count -gt 0) {
    Write-Warning "No hourly rows returned for $($emptyMachines.Count) machines:"
    $emptyMachines | Format-Table -AutoSize
}

if ($failures.Count -gt 0) {
    Write-Warning "Some machines failed:"
    $failures | Format-Table -AutoSize
}
