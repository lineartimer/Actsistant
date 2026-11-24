Write-Host ""
Write-Host "Cleaning up..."
Write-Host ""

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

$root = Join-Path $PSScriptRoot "..\.."
$src = Join-Path $root "src"

$dirs = @(
    (Join-Path $root ".claude"),
    (Join-Path $src ".venv"),
    (Join-Path $src "__pycache__"),
    (Join-Path $src ".pytest_cache"),
    (Join-Path $src "api\__pycache__"),
    (Join-Path $src "core\__pycache__"),
    (Join-Path $src "core\agents\__pycache__"),
    (Join-Path $src "core\tools\__pycache__"),
    (Join-Path $src "database\__pycache__"),
    (Join-Path $src "tests\unit_tests\__pycache__"),
    (Join-Path $src "tests\integration_tests\__pycache__")
)
foreach ($d in $dirs) {
    Remove-Item -Path $d -Recurse -Force -ErrorAction SilentlyContinue
}

Remove-Item -Path (Join-Path $src "database\*.xhtml") -Force -ErrorAction SilentlyContinue
Remove-Item -Path (Join-Path $src "tests\integration_tests\test_act.md") -Force -ErrorAction SilentlyContinue

Wait-KeyPress
