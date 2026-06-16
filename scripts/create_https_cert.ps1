param(
    [string]$OutDir = "local-certs",
    [string[]]$IpAddresses = @("192.168.137.1", "127.0.0.1"),
    [string[]]$DnsNames = @("localhost"),
    [switch]$InstallRootForCurrentUser
)

$ErrorActionPreference = "Stop"

function ConvertTo-DerLength {
    param([int]$Length)

    if ($Length -lt 128) {
        return [byte[]]@($Length)
    }

    $bytes = New-Object System.Collections.Generic.List[byte]
    $value = $Length
    while ($value -gt 0) {
        $bytes.Insert(0, [byte]($value -band 0xff))
        $value = $value -shr 8
    }
    return [byte[]](@([byte](0x80 -bor $bytes.Count)) + $bytes.ToArray())
}

function Join-ByteArrays {
    param([byte[][]]$Arrays)

    $bytes = New-Object System.Collections.Generic.List[byte]
    foreach ($array in $Arrays) {
        if ($null -ne $array) {
            $bytes.AddRange([byte[]]$array)
        }
    }
    return $bytes.ToArray()
}

function ConvertTo-DerInteger {
    param([byte[]]$Value)

    if ($null -eq $Value -or $Value.Length -eq 0) {
        $Value = [byte[]]@(0)
    }

    $offset = 0
    while ($offset -lt ($Value.Length - 1) -and $Value[$offset] -eq 0) {
        $offset += 1
    }
    if ($offset -gt 0) {
        $Value = [byte[]]$Value[$offset..($Value.Length - 1)]
    }

    if (($Value[0] -band 0x80) -ne 0) {
        $Value = [byte[]](@(0) + $Value)
    }

    return Join-ByteArrays @(
        [byte[]]@(0x02),
        (ConvertTo-DerLength $Value.Length),
        $Value
    )
}

function ConvertTo-DerSequence {
    param([byte[][]]$Children)

    $content = Join-ByteArrays $Children
    return Join-ByteArrays @(
        [byte[]]@(0x30),
        (ConvertTo-DerLength $content.Length),
        $content
    )
}

function ConvertTo-Pem {
    param(
        [string]$Label,
        [byte[]]$Bytes
    )

    $base64 = [Convert]::ToBase64String($Bytes)
    $lines = for ($index = 0; $index -lt $base64.Length; $index += 64) {
        $base64.Substring($index, [Math]::Min(64, $base64.Length - $index))
    }
    return "-----BEGIN $Label-----`n$($lines -join "`n")`n-----END $Label-----`n"
}

function Export-RsaPrivateKeyPem {
    param([System.Security.Cryptography.RSA]$Rsa)

    $parameters = $Rsa.ExportParameters($true)
    $der = ConvertTo-DerSequence @(
        (ConvertTo-DerInteger ([byte[]]@(0))),
        (ConvertTo-DerInteger $parameters.Modulus),
        (ConvertTo-DerInteger $parameters.Exponent),
        (ConvertTo-DerInteger $parameters.D),
        (ConvertTo-DerInteger $parameters.P),
        (ConvertTo-DerInteger $parameters.Q),
        (ConvertTo-DerInteger $parameters.DP),
        (ConvertTo-DerInteger $parameters.DQ),
        (ConvertTo-DerInteger $parameters.InverseQ)
    )
    return ConvertTo-Pem "RSA PRIVATE KEY" $der
}

function Export-CertificatePem {
    param([System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate)

    return ConvertTo-Pem "CERTIFICATE" (
        $Certificate.Export(
            [System.Security.Cryptography.X509Certificates.X509ContentType]::Cert
        )
    )
}

$resolvedOutDir = Join-Path (Get-Location) $OutDir
New-Item -ItemType Directory -Force -Path $resolvedOutDir | Out-Null

$currentIps = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike "169.254.*" -and
        $_.IPAddress -ne "127.0.0.1"
    } |
    Select-Object -ExpandProperty IPAddress

$allIps = @($IpAddresses + $currentIps) |
    Where-Object { $_ } |
    Sort-Object -Unique

$notBefore = [DateTimeOffset]::UtcNow.AddMinutes(-5)
$rootNotAfter = $notBefore.AddYears(5)
$serverNotAfter = $notBefore.AddYears(2)

$hashAlgorithm = [System.Security.Cryptography.HashAlgorithmName]::SHA256
$padding = [System.Security.Cryptography.RSASignaturePadding]::Pkcs1

$rootRsa = [System.Security.Cryptography.RSA]::Create(4096)
$rootRequest = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
    "CN=Process Project Local CA",
    $rootRsa,
    $hashAlgorithm,
    $padding
)
$rootRequest.CertificateExtensions.Add(
    [System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new(
        $true,
        $false,
        0,
        $true
    )
)
$rootRequest.CertificateExtensions.Add(
    [System.Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new(
        [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::KeyCertSign -bor
            [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::CrlSign,
        $true
    )
)
$rootRequest.CertificateExtensions.Add(
    [System.Security.Cryptography.X509Certificates.X509SubjectKeyIdentifierExtension]::new(
        $rootRequest.PublicKey,
        $false
    )
)
$rootCert = $rootRequest.CreateSelfSigned($notBefore, $rootNotAfter)

$serverRsa = [System.Security.Cryptography.RSA]::Create(2048)
$serverRequest = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
    "CN=process-project.local",
    $serverRsa,
    $hashAlgorithm,
    $padding
)
$serverSan = [System.Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new()
foreach ($name in ($DnsNames | Sort-Object -Unique)) {
    $serverSan.AddDnsName($name)
}
foreach ($ip in $allIps) {
    $parsedIp = [System.Net.IPAddress]::Parse($ip)
    $serverSan.AddIpAddress($parsedIp)
}
$serverRequest.CertificateExtensions.Add($serverSan.Build())
$serverRequest.CertificateExtensions.Add(
    [System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new(
        $false,
        $false,
        0,
        $true
    )
)
$serverRequest.CertificateExtensions.Add(
    [System.Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new(
        [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::DigitalSignature -bor
            [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::KeyEncipherment,
        $true
    )
)
$serverEnhancedKeyUsages = [System.Security.Cryptography.OidCollection]::new()
$serverEnhancedKeyUsages.Add(
    [System.Security.Cryptography.Oid]::new("1.3.6.1.5.5.7.3.1")
) | Out-Null
$serverRequest.CertificateExtensions.Add(
    [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]::new(
        $serverEnhancedKeyUsages,
        $false
    )
)

$serial = New-Object byte[] 16
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($serial)
$serverCertPublic = $serverRequest.Create(
    $rootCert,
    $notBefore,
    $serverNotAfter,
    $serial
)

$rootCerPath = Join-Path $resolvedOutDir "process-project-local-ca.cer"
$rootPemPath = Join-Path $resolvedOutDir "process-project-local-ca.pem"
$serverCertPath = Join-Path $resolvedOutDir "process-project-server.crt"
$serverKeyPath = Join-Path $resolvedOutDir "process-project-server.key"

[System.IO.File]::WriteAllBytes(
    $rootCerPath,
    $rootCert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
)
[System.IO.File]::WriteAllText($rootPemPath, (Export-CertificatePem $rootCert))
[System.IO.File]::WriteAllText($serverCertPath, (Export-CertificatePem $serverCertPublic))
[System.IO.File]::WriteAllText($serverKeyPath, (Export-RsaPrivateKeyPem $serverRsa))

if ($InstallRootForCurrentUser) {
    Import-Certificate `
        -FilePath $rootCerPath `
        -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
}

Write-Host "Created HTTPS certificate files:"
Write-Host "  Phone CA certificate: $rootCerPath"
Write-Host "  Server certificate:   $serverCertPath"
Write-Host "  Server private key:   $serverKeyPath"
Write-Host ""
Write-Host "Certificate covers IPs:"
foreach ($ip in $allIps) {
    Write-Host "  https://$ip`:8443"
}
Write-Host ""
Write-Host "Start HTTPS server:"
Write-Host "  .\scripts\start_https_server.ps1 -Port 8443 -CertFile `"$serverCertPath`" -KeyFile `"$serverKeyPath`""
