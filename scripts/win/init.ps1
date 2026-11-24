function Set-TerminalBounds {
    try {
        if (-not ([System.Management.Automation.PSTypeName]'ConsoleWin').Type) {
            Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ConsoleWin {
    [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
}
'@
        }
        Add-Type -AssemblyName System.Windows.Forms
        $area = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea

        $K = 60
        $WW = [int]($area.Width * $K / 100)
        $WH = [int]($area.Height * $K / 100)
        $X = $area.X + [int](($area.Width - $WW) / 2)
        $Y = $area.Y + [int](($area.Height - $WH) / 2)

        $hwnd = [ConsoleWin]::GetConsoleWindow()
        if ($hwnd -eq [IntPtr]::Zero -or -not [ConsoleWin]::IsWindowVisible($hwnd)) {
            $hwnd = [ConsoleWin]::GetForegroundWindow()
        }
        if ($hwnd -ne [IntPtr]::Zero) {
            [void][ConsoleWin]::MoveWindow($hwnd, $X, $Y, $WW, $WH, $true)
        }
    } catch {
        # Window positioning is cosmetic; ignore failures
    }
}

function Start-DockerIfNeeded {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { return $true }

    Write-Host "Starting Docker Desktop..."
    $dockerDesktop = Join-Path $Env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerDesktop)) { return $false }
    Start-Process -FilePath $dockerDesktop
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { return $true }
    }
    return $false
}

function Wait-KeyPress {
    Write-Host ""
    Write-Host "Press any key to continue..."
    try {
        [void]$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    } catch {
        [void](Read-Host)
    }
}

Set-TerminalBounds

Set-Location (Join-Path $PSScriptRoot "..\..\src")

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m venv .venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python -m venv .venv
} else {
    Write-Host "Error: Python 3 is not installed."
}

$venvPython = Join-Path $PWD.Path ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
} else {
    Write-Host "Error: the virtual environment could not be created."
}

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    ollama pull qwen3-embedding:0.6b
    ollama pull qwen3:8b
} else {
    Write-Host "Error: Ollama is not installed."
}

if (Start-DockerIfNeeded) {
    # The compose file lives in the repo root
    Push-Location ..
    docker compose down -v --remove-orphans
    docker compose up -d weaviate
    Pop-Location
} else {
    Write-Host "Error: Docker could not be started."
}

Wait-KeyPress
