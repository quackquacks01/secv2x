$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "[1/5] Checking required files..." -ForegroundColor Cyan
$files = @(
    "capture.nod.xml",
    "capture.edg.xml",
    "capture.rou.xml",
    "capture.add.xml",
    "capture.view.xml",
    "capture.sumocfg"
)
foreach ($file in $files) {
    if (-not (Test-Path $file)) {
        throw "Missing file: $file"
    }
}

Write-Host "[2/5] Validating XML syntax..." -ForegroundColor Cyan
foreach ($file in $files) {
    try {
        [xml](Get-Content -Raw -Encoding UTF8 $file) | Out-Null
        Write-Host "  OK $file"
    }
    catch {
        throw "XML validation failed: $file`n$($_.Exception.Message)"
    }
}

if (-not (Get-Command netconvert -ErrorAction SilentlyContinue)) {
    throw "netconvert was not found in PATH. Open the SUMO command prompt or add SUMO/bin to PATH."
}
if (-not (Get-Command sumo -ErrorAction SilentlyContinue)) {
    throw "sumo was not found in PATH."
}
if (-not (Get-Command sumo-gui -ErrorAction SilentlyContinue)) {
    throw "sumo-gui was not found in PATH."
}

Write-Host "[3/5] Rebuilding the network without guessed pedestrian walking areas..." -ForegroundColor Cyan
& netconvert `
    --node-files "capture.nod.xml" `
    --edge-files "capture.edg.xml" `
    --output-file "capture.net.xml" `
    --tls.guess true `
    --tls.layout opposites `
    --no-turnarounds true

if ($LASTEXITCODE -ne 0) {
    throw "netconvert failed with exit code $LASTEXITCODE"
}

Write-Host "[4/5] Checking routes and simulation inputs..." -ForegroundColor Cyan

& sumo `
    -c "capture.sumocfg" `
    --ignore-route-errors false `
    --begin 0 `
    --end 1 `
    --no-step-log true

if ($LASTEXITCODE -ne 0) {
    throw "SUMO input/route validation failed with exit code $LASTEXITCODE"
}

Write-Host "[5/5] Launching the paper-capture scenario..." -ForegroundColor Green
& sumo-gui -c "capture.sumocfg" --start --quit-on-end false
