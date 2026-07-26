$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootDir

$PythonCandidates = @(
    @("py", "-3.11"),
    @("py", "-3.12"),
    @("python", "")
)

$PythonCommand = $null
foreach ($Candidate in $PythonCandidates) {
    $Exe = $Candidate[0]
    $Arg = $Candidate[1]
    try {
        if ($Arg) {
            & $Exe $Arg --version | Out-Null
            $PythonCommand = @($Exe, $Arg)
        } else {
            & $Exe --version | Out-Null
            $PythonCommand = @($Exe)
        }
        break
    } catch {
        continue
    }
}

if (-not $PythonCommand) {
    Write-Error "Python 3.11 or 3.12 is required. Install one, then rerun this script."
}

$PythonExe = $PythonCommand[0]
$PythonArgs = @()
if ($PythonCommand.Length -gt 1) {
    $PythonArgs = $PythonCommand[1..($PythonCommand.Length - 1)]
}

& $PythonExe @PythonArgs -m venv .venv-windows
& .\.venv-windows\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-windows\Scripts\python.exe -m pip install -r backend\requirements.txt
& .\.venv-windows\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

Write-Host "Windows environment ready: .venv-windows"
Write-Host "Activate with: .\.venv-windows\Scripts\Activate.ps1"
