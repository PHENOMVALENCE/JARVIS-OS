# Code signing

An unsigned Windows installer triggers SmartScreen: a blue full-screen warning
saying "Windows protected your PC", with the Run button hidden behind "More
info". Most people stop there. It is the single largest obstacle between this
project and somebody else using it, and no amount of code fixes it — it needs a
certificate issued to a verified identity.

The build already signs when a certificate is available. `Build-Release.ps1`
checks for `JARVIS_SIGN_CERTIFICATE` and signs the executable with `signtool`
when it is set, so obtaining a certificate is the only remaining step.

## What SmartScreen actually checks

Two separate things, and confusing them wastes money:

**Is it signed by a verified publisher?** A certificate answers this. An
Organisation Validation (OV) certificate proves an organisation exists; an
Extended Validation (EV) certificate proves it more thoroughly.

**Does this specific binary have reputation?** SmartScreen also tracks how
often a given signed binary has been downloaded and run without incident. A
brand-new OV-signed installer still warns until it accumulates reputation,
which takes downloads over time. EV certificates start with reputation
immediately, which is the main reason they cost more.

So an OV certificate removes the "unknown publisher" warning but may not remove
the SmartScreen prompt on day one. An EV certificate removes both.

## Options

| Route | Cost | Removes SmartScreen immediately | Notes |
|---|---|---|---|
| **SignPath Foundation** | Free for OSS | Depends on their certificate | Purpose-built for open-source projects; signs from CI |
| **Azure Trusted Signing** | ~$10/month | Not immediately (OV-class) | Microsoft's own service; requires a verified Azure account and 3 years of business history, or individual verification |
| **Certum Open Source** | ~€25/year | No | Cheapest real certificate; issued to individuals |
| **DigiCert / Sectigo OV** | ~$200-400/year | No | Standard commercial OV |
| **DigiCert / Sectigo EV** | ~$400-700/year | **Yes** | Requires a hardware token or cloud HSM |
| **Self-signed** | Free | No | Useless for distribution; see below for the one case it helps |

Since 2023, all publicly trusted code signing certificates must have their
private keys on hardware — a USB token, or an HSM-backed cloud service. You
cannot simply download a `.pfx` and use it. That affects how CI signing works:
the key stays in a service and the build calls out to it.

### The route worth trying first

**[SignPath Foundation](https://signpath.org/foundation)** provides free code
signing to open-source projects. This repository qualifies on the obvious
criteria — MIT licensed, public source, reproducible build from CI. Their
process is an application, not a purchase, and signing happens inside their
service from a GitHub Actions workflow, so no key ever touches a developer
machine.

If that is declined, **Certum's Open Source certificate** is the cheapest real
option at roughly €25/year and is issued to an individual rather than a
company, which matters when there is no registered business.

## What I could not do

I cannot obtain a certificate. Every route requires a payment and a verified
identity — a passport or company registration submitted to a certificate
authority. Both are yours to give, not mine, and I will not enter payment or
identity details on your behalf.

What is done: the build signs automatically when a certificate exists, the
release workflow publishes SHA-256 checksums so downloads can be verified
without one, and the README says plainly that the installer is unsigned rather
than letting people discover it at the SmartScreen prompt.

## Once you have a certificate

**Locally**, set two environment variables and rebuild:

```powershell
$env:JARVIS_SIGN_CERTIFICATE = "C:\path\to\certificate.pfx"
$env:JARVIS_SIGN_PASSWORD = "..."
.\Build-Release.ps1
```

**In CI**, add the certificate and password as repository secrets and give the
release workflow this step before it builds the installer:

```yaml
- name: Sign the executable
  env:
    JARVIS_SIGN_CERTIFICATE: ${{ secrets.SIGN_CERTIFICATE_PATH }}
    JARVIS_SIGN_PASSWORD: ${{ secrets.SIGN_PASSWORD }}
  run: |
    & "${env:ProgramFiles(x86)}\Windows Kits\10\bin\x64\signtool.exe" sign `
      /f $env:JARVIS_SIGN_CERTIFICATE /p $env:JARVIS_SIGN_PASSWORD `
      /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
      dist\JARVIS\JARVIS.exe
```

Sign the **installer** as well as the executable. Users run the installer, so
that is the binary SmartScreen judges.

Always timestamp (`/tr`). Without it, every signature stops validating the day
the certificate expires, including on copies already installed.

## Verifying a download without a certificate

Until then, each release publishes `SHA256SUMS.txt`. Verify before running:

```powershell
Get-FileHash .\JARVIS-Setup-x64.exe -Algorithm SHA256
```

Compare the result to the line in `SHA256SUMS.txt`. This proves the file was
not altered in transit. It does not prove who built it — that is what signing
adds.

## Self-signed certificates

Worth exactly one thing: testing that the signing step in the build works
before paying for a real certificate. A self-signed binary is still untrusted
on every machine but the one that created the certificate, so never ship one.

```powershell
$cert = New-SelfSignedCertificate -Type CodeSigningCert `
    -Subject "CN=JARVIS Test" -CertStoreLocation Cert:\CurrentUser\My
Export-PfxCertificate -Cert $cert -FilePath test-cert.pfx `
    -Password (ConvertTo-SecureString -String "test" -Force -AsPlainText)
```

Add `test-cert.pfx` to `.gitignore`. It is a private key.
