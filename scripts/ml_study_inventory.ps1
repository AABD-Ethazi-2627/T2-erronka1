param([Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputPath) { throw 'Inventory output already exists' }
$cpu = Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
$ram = Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory
$video = Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion
$disk = Get-PSDrive -PSProvider FileSystem | Select-Object Name,Used,Free
$gpu = & nvidia-smi '--query-gpu=name,memory.total,memory.used,memory.free,driver_version' '--format=csv,noheader'
if ($LASTEXITCODE -ne 0) { throw 'GPU inventory failed' }
$record = [ordered]@{
    captured_at = (Get-Date).ToUniversalTime().ToString('o')
    note = 'Snapshot during the single active local pilot; desktop workloads preserved'
    cpu = $cpu
    ram_kib = $ram
    graphics = $video
    disks_bytes = $disk
    nvidia_smi = $gpu
    wsl_observation = 'FedoraLinux-43 WSL2: same RTX5070Ti visible; existing ~7943MiB RAM limit; no configuration change'
    limits = @{ experiment_rss_gib=2; host_available_gib=4; experiment_vram_gib=4; gpu_free_gib=6; evidence_gib=2; disk_free_gib=10 }
}
$record | ConvertTo-Json -Depth 6 | Out-File -LiteralPath $OutputPath -Encoding utf8NoBOM -NoClobber
