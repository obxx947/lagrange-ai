' ============================================================
' 拉格朗日AI — VBScript 工具脚本
' 功能：检查服务状态、端口监听、进程管理
' 用法：cscript //Nologo utils.vbs [status|port|kill]
' ============================================================

Option Explicit
Dim WshShell, fso, cmd, arg

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

If WScript.Arguments.Count = 0 Then
    WScript.Echo "用法: cscript utils.vbs [status|port|kill|info|ip]"
    WScript.Quit
End If

arg = LCase(WScript.Arguments(0))

Select Case arg
    Case "status"
        CheckServiceStatus
        
    Case "port"
        CheckPortListening 3000
        
    Case "kill"
        KillPythonProcesses
        
    Case "info"
        ShowSystemInfo
        
    Case "ip"
        ShowNetworkInfo
        
    Case Else
        WScript.Echo "未知命令: " & arg
End Select

' 检查服务是否运行
Sub CheckServiceStatus()
    Dim exec, output
    Set exec = WshShell.Exec("netstat -ano | findstr :3000")
    output = exec.StdOut.ReadAll()
    If Len(output) > 0 Then
        WScript.Echo "[运行中] 端口3000正在监听"
        WScript.Echo output
    Else
        WScript.Echo "[已停止] 端口3000未监听"
    End If
End Sub

' 检查端口
Sub CheckPortListening(port)
    Dim exec, output
    Set exec = WshShell.Exec("netstat -ano | findstr :" & port)
    output = exec.StdOut.ReadAll()
    If Len(output) > 0 Then
        WScript.Echo "[OK] 端口 " & port & " 正在监听"
    Else
        WScript.Echo "[STOP] 端口 " & port & " 未监听"
    End If
End Sub

' 终止Python进程
Sub KillPythonProcesses()
    Dim exec
    Set exec = WshShell.Exec("taskkill /F /IM python.exe 2>nul")
    WScript.Echo "[完成] Python进程已终止"
End Sub

' 系统信息
Sub ShowSystemInfo()
    Dim net, ip
    Set net = CreateObject("WScript.Network")
    WScript.Echo "计算机名: " & net.ComputerName
    WScript.Echo "用户名:   " & net.UserName
    WScript.Echo "域名:     " & net.UserDomain
End Sub

' 网络信息
Sub ShowNetworkInfo()
    Dim exec, output, lines, line, ip
    Set exec = WshShell.Exec("ipconfig")
    output = exec.StdOut.ReadAll()
    lines = Split(output, vbCrLf)
    For Each line In lines
        If InStr(line, "IPv4") > 0 Or InStr(line, "IP Address") > 0 Then
            WScript.Echo Trim(line)
        End If
    Next
End Sub
