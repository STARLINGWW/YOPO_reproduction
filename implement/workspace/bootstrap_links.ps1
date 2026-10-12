# Recreate the implement/workspace code view with NTFS junctions (Windows).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $here "..\..")).Path
foreach ($name in @("src","scripts","configs","docker","ros2_ws","tests","external","benchmarks","vendor","assets")) {
    $link = Join-Path $here $name
    $target = Join-Path $root $name
    if (Test-Path $link) { Write-Host "exists: $name"; continue }
    if (-not (Test-Path $target)) { Write-Host "missing target: $name"; continue }
    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    Write-Host "linked: $name -> $target"
}
