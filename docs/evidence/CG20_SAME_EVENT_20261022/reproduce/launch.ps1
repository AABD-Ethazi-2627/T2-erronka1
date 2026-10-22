param([Parameter(Mandatory=$true)][string]$Name, [Parameter(ValueFromRemainingArguments=$true)][string[]]$TaskArgs)
$ErrorActionPreference = 'Stop'
$taskRoot = 'D:\github\_local\t2-babysit-20261021\cg20-api-kibana-20261022'
$linuxRoot = '/mnt/d/github/_local/t2-babysit-20261021/cg20-api-kibana-20261022'
$log = Join-Path $taskRoot ($Name + '.log')
if (Test-Path -LiteralPath $log) { throw "Refusing to replace $log" }
$psi = [System.Diagnostics.ProcessStartInfo]::new('C:\Windows\System32\wsl.exe')
$psi.UseShellExecute = $false
$psi.WorkingDirectory = 'D:\github'
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
foreach ($arg in @('-d','FedoraLinux-43','--cd','/mnt/d/github/_worktrees/t2-cg20-api-kibana-20261022','--exec','env',"TMP=$linuxRoot/process-temp","TEMP=$linuxRoot/process-temp","TMPDIR=$linuxRoot/process-temp",'PYTHONDONTWRITEBYTECODE=1','PYTHONUTF8=1',"PYTHONPATH=/mnt/d/github/_worktrees/t2-cg20-api-kibana-20261022:/mnt/d/github/_worktrees/t2-cg20-api-kibana-20261022/tests",'OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1',"UV_CACHE_DIR=$linuxRoot/uv-cache","RUFF_CACHE_DIR=$linuxRoot/ruff-cache",'/home/Fedora/t2-real-lab-20261022/venv/bin/python','-B')) { $psi.ArgumentList.Add($arg) }
foreach ($arg in $TaskArgs) { $psi.ArgumentList.Add($arg.Replace('TASKROOT',$linuxRoot)) }
$p = [System.Diagnostics.Process]::Start($psi)
$outTask = $p.StandardOutput.ReadToEndAsync()
$errTask = $p.StandardError.ReadToEndAsync()
$p.WaitForExit()
$result = [ordered]@{name=$Name; argv=@($psi.ArgumentList); exit=$p.ExitCode; utc=[DateTimeOffset]::UtcNow.ToString('o')}
[IO.File]::WriteAllText($log, $outTask.Result + "`nSTDERR`n" + $errTask.Result)
Add-Content -LiteralPath (Join-Path $taskRoot 'commands.jsonl') -Value ($result | ConvertTo-Json -Compress -Depth 6)
Get-Content -LiteralPath $log -Tail 18
exit $p.ExitCode
