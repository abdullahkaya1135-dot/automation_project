param(
    [string]$HostName = "0.0.0.0",
    [int]$Port = 8443,
    [Parameter(Mandatory = $true)]
    [string]$CertFile,
    [Parameter(Mandatory = $true)]
    [string]$KeyFile
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $CertFile)) {
    throw "Certificate file not found: $CertFile"
}

if (-not (Test-Path -LiteralPath $KeyFile)) {
    throw "Key file not found: $KeyFile"
}

python -m uvicorn app.main:app `
    --host $HostName `
    --port $Port `
    --ssl-certfile $CertFile `
    --ssl-keyfile $KeyFile
