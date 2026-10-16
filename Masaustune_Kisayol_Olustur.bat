@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo Masaüstüne Translito kısayolu oluşturuluyor...
set SCRIPT="%TEMP%\create_translito_shortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT%
echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\Translito.lnk" >> %SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
echo oLink.TargetPath = "%~dp0Baslat.bat" >> %SCRIPT%
echo oLink.WorkingDirectory = "%~dp0" >> %SCRIPT%
echo oLink.Description = "Translito - Ekran ve Oyun Çevirici" >> %SCRIPT%
echo oLink.Save >> %SCRIPT%
cscript /nologo %SCRIPT%
del %SCRIPT%

echo.
echo [BAŞARILI] Masaüstünüze "Translito" kısayolu eklendi!
pause
