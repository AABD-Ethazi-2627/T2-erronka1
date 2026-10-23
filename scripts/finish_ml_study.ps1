param(
    [Parameter(Mandatory=$true)][string]$StudyRoot,
    [string]$AnalysisName = 'analysis-v1',
    [string]$PythonPath = 'D:\cnc-guard-research\venv-20261023\Scripts\python.exe'
)
$ErrorActionPreference='Stop'
if (!(Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'Research Python missing' }
$analysisPath=Join-Path $StudyRoot $AnalysisName
if (Test-Path -LiteralPath $analysisPath) { throw 'Choose a fresh analysis destination' }
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
function Invoke-AccountedStudyModule {
    param([string]$Module,[string[]]$Arguments)
    $nativeArgs=@('-m','scripts.account_ml_study','--root',$StudyRoot,'--module',$Module,'--')+$Arguments
    & $PythonPath @nativeArgs
    if ($LASTEXITCODE -ne 0) { throw "Failed: $Module; inspect preserved logs before retrying" }
}
Invoke-AccountedStudyModule 'scripts.report_ml_study' @('--output',$StudyRoot,'--destination',$analysisPath)
Invoke-AccountedStudyModule 'scripts.verify_ml_study_scores' @('--root',$StudyRoot,'--destination',(Join-Path $analysisPath 'native-score-verification.json'))
Invoke-AccountedStudyModule 'scripts.explain_ml_study' @('--root',$StudyRoot,'--summary',(Join-Path $analysisPath 'summary.json'),'--destination',(Join-Path $analysisPath 'explanations.json'))
Invoke-AccountedStudyModule 'scripts.export_ml_study_package' @('--root',$StudyRoot,'--destination',(Join-Path $analysisPath 'packages'))
Invoke-AccountedStudyModule 'scripts.audit_ml_study' @('--root',$StudyRoot,'--summary',(Join-Path $analysisPath 'summary.json'),'--destination',(Join-Path $analysisPath 'independent-arithmetic-audit.json'))
