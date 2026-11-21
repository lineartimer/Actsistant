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

$venvPython = Join-Path $PWD.Path ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Error: .venv not found. Run init.ps1 first."
    Wait-KeyPress
    exit 1
}

$envFile = Join-Path $PWD.Path ".env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        $line = $line.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { continue }
        if ($line -match '^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $name = $Matches[1]
            $value = $Matches[2].Trim()
            if ($value -match '^"(.*)"$' -or $value -match "^'(.*)'$") { $value = $Matches[1] }
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

Write-Host ""
Write-Host "Service running at: http://127.0.0.1:5005"
Write-Host ""

& $venvPython -m uvicorn main:app --host 127.0.0.1 --port 5005
