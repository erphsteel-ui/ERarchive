param([string]$ServerUrl = 'http://127.0.0.1:8080/widget')

# Keep this script ASCII for compatibility with Windows PowerShell 5.1.
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class WidgetWin32 {
    public delegate bool EnumWindowsProc(IntPtr window, IntPtr data);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr data);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr window, StringBuilder text, int length);
    [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr window);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
    [DllImport("user32.dll", EntryPoint="GetWindowLongW")] public static extern int GetWindowLong(IntPtr window, int index);
    [DllImport("user32.dll", EntryPoint="SetWindowLongW")] public static extern int SetWindowLong(IntPtr window, int index, int value);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int width, int height, uint flags);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr window, uint message, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int MessageBox(IntPtr window, string text, string caption, uint type);
}
'@

try {
    $uri = [Uri]$ServerUrl
    if ($uri.Scheme -notin @('http', 'https')) { throw 'Use an http or https widget URL.' }
    $token = [Guid]::NewGuid().ToString('N')
    $builder = [UriBuilder]::new($uri)
    $query = $builder.Query.TrimStart('?')
    if ($query) { $query += '&' }
    $builder.Query = $query + 'widget_instance=' + $token
    $title = 'ERWIDGET-' + $token
    $closeTitle = 'ERWIDGET-CLOSE-' + $token

    $edge = (Get-Command msedge.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
    if (-not $edge) {
        $paths = @(
            (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
            (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
            (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\Application\msedge.exe')
        )
        $edge = $paths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $edge) { throw 'Microsoft Edge could not be found.' }
    $appArgument = '--app=' + $builder.Uri.AbsoluteUri
    Start-Process -FilePath $edge -ArgumentList @($appArgument, '--window-size=1150,520', '--window-position=720,40')

    $script:widgetHandle = [IntPtr]::Zero
    $callback = [WidgetWin32+EnumWindowsProc]{
        param([IntPtr]$handle, [IntPtr]$unused)
        if (-not [WidgetWin32]::IsWindowVisible($handle)) { return $true }
        $buffer = [Text.StringBuilder]::new(512)
        [void][WidgetWin32]::GetWindowText($handle, $buffer, $buffer.Capacity)
        if ($buffer.ToString() -ne $title) { return $true }
        [uint32]$processId = 0
        [void][WidgetWin32]::GetWindowThreadProcessId($handle, [ref]$processId)
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process -and $process.ProcessName -eq 'msedge') {
            $script:widgetHandle = $handle
            return $false
        }
        return $true
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    while ($script:widgetHandle -eq [IntPtr]::Zero -and [DateTime]::UtcNow -lt $deadline) {
        [void][WidgetWin32]::EnumWindows($callback, [IntPtr]::Zero)
        if ($script:widgetHandle -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 250 }
    }
    if ($script:widgetHandle -eq [IntPtr]::Zero) { throw 'Widget window was not found. Check that the server is reachable.' }

    $handle = $script:widgetHandle
    $style = [WidgetWin32]::GetWindowLong($handle, -16)
    [void][WidgetWin32]::SetWindowLong($handle, -16, ($style -band (-bnot 0x00C40000)))
    # HWND_BOTTOM; keep size/position, do not activate, and refresh the frame.
    [void][WidgetWin32]::SetWindowPos($handle, [IntPtr]1, 0, 0, 0, 0, 0x0027)
    while ([WidgetWin32]::IsWindow($handle)) {
        $buffer = [Text.StringBuilder]::new(512)
        [void][WidgetWin32]::GetWindowText($handle, $buffer, $buffer.Capacity)
        if ($buffer.ToString() -eq $closeTitle) {
            [void][WidgetWin32]::PostMessage($handle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
            break
        }
        [void][WidgetWin32]::SetWindowPos($handle, [IntPtr]1, 0, 0, 0, 0, 0x0013)
        Start-Sleep -Milliseconds 500
    }
} catch {
    [void][WidgetWin32]::MessageBox([IntPtr]::Zero, $_.Exception.Message, 'ER Widget', 0x10)
}
