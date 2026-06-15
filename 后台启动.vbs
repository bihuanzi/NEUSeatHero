' ============================================
' Seat Grabber v1.0 - 后台静默启动器
' 双击此文件即可在后台运行，不会弹出任何窗口
' ============================================

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

' 读取配置文件
qqFile = dir & "\qq.txt"
authFile = dir & "\auth.txt"

qq = ""
auth = ""
keyword = ""

If fso.FileExists(qqFile) Then
    Set f = fso.OpenTextFile(qqFile, 1, False, 0)  ' 0 = ASCII
    If Not f.AtEndOfStream Then qq = Trim(f.ReadLine())
    f.Close
End If

If fso.FileExists(authFile) Then
    Set f = fso.OpenTextFile(authFile, 1, False, 0)
    If Not f.AtEndOfStream Then auth = Trim(f.ReadLine())
    f.Close
End If

' 构建命令
ps1 = dir & "\run.ps1"
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"

If qq <> "" Then
    cmd = cmd & " -QQUser """ & qq & """ -QQAuthCode """ & auth & """ -Keyword """ & keyword & """"
End If

' RunMode: 0=隐藏窗口, False=不等待
shell.Run cmd, 0, False
