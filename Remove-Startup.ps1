$ErrorActionPreference = "Stop"
$TaskName = "J.A.R.V.I.S Mark 6"
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "J.A.R.V.I.S startup disabled."
} else {
    Write-Host "J.A.R.V.I.S startup was not enabled."
}
