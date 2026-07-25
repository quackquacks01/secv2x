[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [string]$GccPath = "C:\msys64\ucrt64\bin\gcc.exe"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$SourceRoot = Join-Path $ProjectRoot "kpqc-work\AIMer\Reference_Implementation"
$Wrapper = Join-Path $ProjectRoot "native\aimer\aimer_128f_wrapper.c"
$OutputDir = Join-Path $ProjectRoot "native\aimer"
$OutputDll = Join-Path $OutputDir "libaimer-128f.dll"

if (-not (Test-Path $GccPath)) {
    throw "GCC not found: $GccPath"
}
if (-not (Test-Path $SourceRoot)) {
    throw "AIMer source not found: $SourceRoot"
}
if (-not (Test-Path $Wrapper)) {
    throw "AIMer wrapper not found: $Wrapper"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$sources = @(
    $Wrapper,
    (Join-Path $SourceRoot "aim2.c"),
    (Join-Path $SourceRoot "hash.c"),
    (Join-Path $SourceRoot "sign.c"),
    (Join-Path $SourceRoot "tree.c"),
    (Join-Path $SourceRoot "field128.c"),
    (Join-Path $SourceRoot "common\aes.c"),
    (Join-Path $SourceRoot "common\fips202.c"),
    (Join-Path $SourceRoot "common\rng.c")
)

$args = @(
    "-shared",
    "-O3",
    "-march=native",
    "-fomit-frame-pointer",
    "-static-libgcc",
    "-DPARAMS=128f",
    "-I$SourceRoot",
    "-o", $OutputDll
) + $sources + @("-lbcrypt")

Write-Host "[1/3] Building AIMer-128f DLL..."
& $GccPath @args
if ($LASTEXITCODE -ne 0) {
    throw "AIMer DLL build failed with exit code $LASTEXITCODE"
}

Write-Host "[2/3] Verifying output..."
if (-not (Test-Path $OutputDll)) {
    throw "DLL was not created: $OutputDll"
}

$Objdump = Join-Path (Split-Path $GccPath) "objdump.exe"
if (Test-Path $Objdump) {
    $exports = & $Objdump -p $OutputDll |
        Select-String "kpqc_aimer_128f_(publickeybytes|secretkeybytes|signaturebytes|keypair|signature|verify)"
    if ($exports.Count -lt 6) {
        throw "Expected AIMer wrapper exports were not found."
    }
    $exports | ForEach-Object { Write-Host $_.Line }
}

Write-Host "[3/3] AIMer DLL ready: $OutputDll"
