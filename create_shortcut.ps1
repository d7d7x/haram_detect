$wsh = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path -Path $desktop -ChildPath "Media Sanitizer Pro.lnk"
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "G:\antigravity\ChangeSup\media_sanitizer\run_app.bat"
$shortcut.WorkingDirectory = "G:\antigravity\ChangeSup\media_sanitizer"
$shortcut.IconLocation = "shell32.dll, 137"
$shortcut.Save()
Write-Host "Desktop shortcut created successfully!"
