Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c ""%~dp0run_app.bat""", 0, False
