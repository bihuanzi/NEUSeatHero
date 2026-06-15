# Auto Page Refresher - Seat Grabber v1.0
# Monitors a webpage and sends QQ notification when target element appears.
# Usage: Double-click .bat, or: .\run.ps1 -Keyword "target" -QQUser "123" -QQAuthCode "xxx"

param(
    [string]$WindowTitle = "*Edge*",
    [int]$MinInterval = 60,
    [int]$MaxInterval = 120,
    [double]$SkipProbability = 0.05,
    [string]$Keyword = "",
    [string]$QQUser = "",
    [string]$QQAuthCode = "",
    [string]$NotifyTo = ""
)

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class W32 {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")]
    public static extern bool IsIconic(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    public const int SW_RESTORE = 9;
}
'@

$wshell = New-Object -ComObject WScript.Shell
$notifyEnabled = ($Keyword -ne "" -and $QQUser -ne "" -and $QQAuthCode -ne "")
if ($NotifyTo -eq "") { $NotifyTo = "${QQUser}@qq.com" }

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $c = "Green"
    if ($Level -eq "WARN")  { $c = "Yellow" }
    if ($Level -eq "ERROR") { $c = "Red" }
    if ($Level -eq "SKIP")  { $c = "DarkGray" }
    if ($Level -eq "FOUND") { $c = "Magenta" }
    Write-Host "[$ts] [$Level] $Message" -ForegroundColor $c
}

function Find-WindowTitle {
    param([string]$Pattern)
    $re = $Pattern -replace '\*','.*' -replace '\?','.'
    $found = @()
    $ps = Get-Process | Where-Object { $_.MainWindowTitle -match $re -and $_.MainWindowTitle.Length -gt 0 }
    foreach ($p in $ps) { $found += $p.MainWindowTitle }
    return $found
}

function Get-BrowserHandle {
    $browsers = @("msedge", "chrome")
    foreach ($b in $browsers) {
        $proc = Get-Process -Name $b -ErrorAction SilentlyContinue | 
                Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero -and $_.MainWindowTitle.Length -gt 0 } |
                Select-Object -First 1
        if ($proc) { return $proc.MainWindowHandle }
    }
    return [IntPtr]::Zero
}

function Activate-Browser {
    $hwnd = Get-BrowserHandle
    if ($hwnd -eq [IntPtr]::Zero) { return $false }
    try {
        if ([W32]::IsIconic($hwnd)) {
            [W32]::ShowWindow($hwnd, [W32]::SW_RESTORE) | Out-Null
            Start-Sleep -Milliseconds 300
        }
        [W32]::SetForegroundWindow($hwnd) | Out-Null
        Start-Sleep -Milliseconds (Get-Random -Min 400 -Max 900)
        return $true
    } catch {
        return $false
    }
}

function Restore-ForegroundWindow {
    param([IntPtr]$hWnd)
    if ($hWnd -ne [IntPtr]::Zero) {
        [W32]::SetForegroundWindow($hWnd) | Out-Null
    }
}

function Send-Key {
    param([string]$Key)
    $wshell.SendKeys($Key)
}

function Get-PageText {
    try { Set-Clipboard -Value " " } catch { }

    $jsCode = 'try{var xp="//*[@id=\"contentFrame\"]/section/div[2]/div[2]/div/div[2]/div[1]/input[2]";var el=document.evaluate(xp,document,null,9,null).singleNodeValue;if(el){copy("FOUND:"+(el.value||el.outerHTML||"EXISTS"));}else{var el2=document.getElementById("contentFrame");if(!el2){copy("NOT_FOUND: contentFrame missing");}else{var d=el2.contentDocument||el2.contentWindow;if(d&&d.document){d=d.document;}var el3=d?d.evaluate("/section/div[2]/div[2]/div/div[2]/div[1]/input[2]",d,null,9,null).singleNodeValue:null;copy(el3?"FOUND_IN_FRAME:"+el3.value:"NOT_FOUND: tag="+el2.tagName+" id="+el2.id);}}}catch(e){copy("ERR:"+e.message);}'
    Set-Clipboard -Value $jsCode

    Send-Key -Key "^+j"
    Start-Sleep -Milliseconds 600
    Send-Key -Key "^v"
    Start-Sleep -Milliseconds 200
    Send-Key -Key "{ENTER}"
    Start-Sleep -Milliseconds 600
    Send-Key -Key "{F12}"
    Start-Sleep -Milliseconds 200

    try {
        $text = Get-Clipboard -Raw
        if ($text -and $text.Length -gt 0 -and $text -ne $jsCode) { return $text }
    } catch { }

    # Fallback: Ctrl+U page source
    try { Set-Clipboard -Value " " } catch { }
    Send-Key -Key "^u"
    Start-Sleep -Milliseconds 1500
    Send-Key -Key "^{END}"
    Start-Sleep -Milliseconds 150
    Send-Key -Key "^a"
    Start-Sleep -Milliseconds 200
    Send-Key -Key "^c"
    Start-Sleep -Milliseconds 200
    Send-Key -Key "^w"
    Start-Sleep -Milliseconds 200

    try {
        $text = Get-Clipboard -Raw
        if ($text -and $text.Length -gt 10) { return $text }
    } catch { }

    return ""
}

function Send-QQMail {
    param([string]$FoundText)
    try {
        $smtpServer = "smtp.qq.com"
        $smtpPort = 587
        $from = "${QQUser}@qq.com"
        $subject = "[Alert] Keyword '$Keyword' Detected!"
        $body = @"
Keyword "$Keyword" was found on the page at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss').

Matched content (first 500 chars):
----------------------------------------
$($FoundText.Substring(0, [Math]::Min(500, $FoundText.Length)))
----------------------------------------

This is an auto-notification from Seat Grabber v1.0.
"@

        $mail = New-Object System.Net.Mail.MailMessage
        $mail.From = $from
        $mail.To.Add($NotifyTo)
        $mail.Subject = $subject
        $mail.Body = $body
        $mail.BodyEncoding = [System.Text.Encoding]::UTF8
        $mail.SubjectEncoding = [System.Text.Encoding]::UTF8

        $smtp = New-Object System.Net.Mail.SmtpClient($smtpServer, $smtpPort)
        $smtp.EnableSsl = $true
        $smtp.Credentials = New-Object System.Net.NetworkCredential($from, $QQAuthCode)
        $smtp.Send($mail)

        $mail.Dispose()
        $smtp.Dispose()
        return $true
    } catch {
        Write-Log "Send QQ mail failed: $_" -Level "ERROR"
        return $false
    }
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Seat Grabber v1.0 - Auto Page Refresher" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

Write-Log "Target window : $WindowTitle"
Write-Log "Interval      : $MinInterval ~ $MaxInterval sec"
Write-Log "Skip chance   : $($SkipProbability * 100)%"
if ($notifyEnabled) {
    Write-Log "Keyword detect: '$Keyword'"
    Write-Log "QQ notify to  : $NotifyTo"
} else {
    Write-Log "QQ notify     : DISABLED"
}
Write-Log "Ctrl+C then Y = exit | any other key = resume" -Level "WARN"
Write-Host ""

[Console]::TreatControlCAsInput = $true

function Sleep-Safe {
    param([double]$Seconds)
    $end = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $end) {
        Start-Sleep -Milliseconds 500
        if ([Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ($key.KeyChar -eq 3) { return "CTRLC" }
        }
    }
    return $null
}

$iteration = 0
$lastFound = [DateTime]::MinValue

while ($true) {
    $iteration++
    Write-Host ("-" * 40)
    Write-Log "Round $iteration started"

    while ([Console]::KeyAvailable) { $null = [Console]::ReadKey($true) }

    $titles = Find-WindowTitle -Pattern $WindowTitle
    if ($titles.Count -eq 0) {
        Write-Log "No matching window found, retrying..." -Level "WARN"
        $null = Sleep-Safe -Seconds (Get-Random -Min 10 -Max 30)
        continue
    }

    $target = $titles[0]
    Write-Log "Found window: '$target'"

    if ((Get-Random -Min 0.0 -Max 1.0) -lt $SkipProbability) {
        Write-Log "Randomly skipped this round" -Level "SKIP"
        $null = Sleep-Safe -Seconds (Get-Random -Min $MinInterval -Max $MaxInterval)
        continue
    }

    # 记住用户当前前台窗口，稍后还原
    $prevHwnd = [W32]::GetForegroundWindow()

    if (-not (Activate-Browser)) {
        Write-Log "Failed to activate browser" -Level "ERROR"
        $null = Sleep-Safe -Seconds (Get-Random -Min $MinInterval -Max $MaxInterval)
        continue
    }
    Write-Log "Browser activated"

    if ((Get-Random -Min 0.0 -Max 1.0) -lt 0.3) {
        Write-Log "Simulating browsing: scrolling..."
        $n = Get-Random -Min 1 -Max 4
        for ($i = 0; $i -lt $n; $i++) {
            $k = if ((Get-Random -Min 0 -Max 2) -eq 0) { "{PGDN}" } else { "{DOWN}" }
            Send-Key -Key $k
            Start-Sleep -Milliseconds (Get-Random -Min 400 -Max 1200)
        }
        if ((Get-Random -Min 0.0 -Max 1.0) -lt 0.5) {
            Send-Key -Key "{UP}"
            Start-Sleep -Milliseconds (Get-Random -Min 200 -Max 600)
        }
    }

    $delay = Get-Random -Min 200 -Max 1000
    Start-Sleep -Milliseconds $delay
    Write-Log ">>> REFRESH (F5) <<<" -Level "WARN"
    Send-Key -Key "{F5}"

    $load = Get-Random -Min 1 -Max 3
    Write-Log "Waiting for page load (${load}s)..."
    $null = Sleep-Safe -Seconds $load

    if ($notifyEnabled) {
        Write-Log "Checking page for keyword: '$Keyword'..."
        $pageText = Get-PageText

        if ($pageText -and $pageText.Length -gt 0) {
            $preview = $pageText.Substring(0, [Math]::Min(120, $pageText.Length)) -replace '\s+', ' '
            Write-Log "Captured $($pageText.Length) chars. Preview: $preview ..."
        } else {
            Write-Log "WARNING: No page text captured!" -Level "WARN"
        }

        if ($pageText -and $pageText.Contains($Keyword)) {
            $matchStart = [Math]::Max(0, $pageText.IndexOf($Keyword) - 50)
            $matchLen = [Math]::Min(500, $pageText.Length - $matchStart)
            $snippet = $pageText.Substring($matchStart, $matchLen)
            
            Write-Log "!!!!! KEYWORD '$Keyword' DETECTED !!!!!" -Level "FOUND"
            Write-Host $snippet -ForegroundColor Yellow
            
            $elapsed = (Get-Date) - $lastFound
            if ($elapsed.TotalMinutes -gt 10) {
                Write-Log "Sending QQ notification..."
                if (Send-QQMail -FoundText $snippet) {
                    Write-Log "QQ notification sent to $NotifyTo!" -Level "FOUND"
                    $lastFound = Get-Date
                }
            } else {
                Write-Log "Notification suppressed (last sent $([math]::Round($elapsed.TotalMinutes,1)) min ago)" -Level "SKIP"
            }
        } else {
            Write-Log "Keyword not found"
        }
    }

    if ((Get-Random -Min 0.0 -Max 1.0) -lt 0.4) {
        Write-Log "Browsing after refresh..."
        $n = Get-Random -Min 1 -Max 5
        for ($i = 0; $i -lt $n; $i++) {
            Send-Key -Key "{DOWN}"
            Start-Sleep -Milliseconds (Get-Random -Min 300 -Max 900)
        }
    }

    $wait = Get-Random -Min $MinInterval -Max $MaxInterval
    $next = (Get-Date).AddSeconds($wait)
    Write-Log "Done. Next refresh at: $($next.ToString('HH:mm:ss'))"
    
    # 把前台窗口还给用户
    Restore-ForegroundWindow -hWnd $prevHwnd
    
    $result = Sleep-Safe -Seconds $wait
    if ($result -eq "CTRLC") {
        Write-Host ""
        Write-Host ">>> Exit? [Y/N]: " -NoNewline -ForegroundColor Yellow
        $confirm = [Console]::ReadKey($false)
        Write-Host ""
        if ($confirm.KeyChar -eq 'y' -or $confirm.KeyChar -eq 'Y') {
            Write-Log "User confirmed exit. Bye!" -Level "WARN"
            break
        }
        Write-Log "Resuming..." -Level "WARN"
    }
}
