Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "G:\antigravity\ChangeSup"
WshShell.Run "pythonw main.py", 0, False
