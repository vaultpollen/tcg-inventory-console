Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & ScriptDir & "\launch_app.bat" & Chr(34), 0
Set WshShell = Nothing
Set FSO = Nothing