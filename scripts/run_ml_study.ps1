param(
    [Parameter(Mandatory=$true)][string]$StudyRoot,
    [string]$PythonPath = 'D:\cnc-guard-research\venv-20261023\Scripts\python.exe',
    [string[]]$Phases = @('screening','nested','calibration','package')
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'Research Python missing' }
if (!(Test-Path -LiteralPath (Join-Path $StudyRoot 'seal.json'))) { throw 'Study is not sealed' }
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$env:TEMP='D:\cnc-guard-research\tmp'
$env:TMP=$env:TEMP
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfff')
foreach ($phase in $Phases) {
    if ($phase -notin @('pilot','screening','nested','calibration','package')) { throw "Unknown phase: $phase" }
    $logPath = Join-Path $StudyRoot "$stamp-$phase.console.log"
    if (Test-Path -LiteralPath $logPath) { throw 'Console log already exists' }
    $nativeArgs = @('-m','scripts.ml_study','run','--output',$StudyRoot,'--phase',$phase)
    & $PythonPath @nativeArgs | Tee-Object -FilePath $logPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
