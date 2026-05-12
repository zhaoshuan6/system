Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

If Not fso.FolderExists(dir & "\logs") Then
    fso.CreateFolder(dir & "\logs")
End If

Dim backendLog, frontendLog
backendLog  = dir & "\logs\backend.log"
frontendLog = dir & "\logs\frontend.log"

' Kill any existing process on port 5000 (old backend) before starting fresh
shell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -ano ^| findstr "":5000 ""') do taskkill /f /pid %a", 0, True

Dim backendCmd, frontendCmd
backendCmd  = "cmd /c cd /d """ & dir & """ && C:\anconda\envs\video_retrieval\python.exe run.py > """ & backendLog & """ 2>&1"
frontendCmd = "cmd /c cd /d """ & dir & "\fronted"" && npm run dev > """ & frontendLog & """ 2>&1"

shell.Run backendCmd, 0, False

WScript.Sleep 15000

shell.Run frontendCmd, 0, False

WScript.Sleep 8000

shell.Run "http://localhost:5173"

MsgBox "System started!" & Chr(13) & Chr(13) & "Frontend : http://localhost:5173" & Chr(13) & "Backend  : http://localhost:5000" & Chr(13) & Chr(13) & "Logs: " & dir & "\logs", 64, "Video Retrieval System"
