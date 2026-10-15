@echo off
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "%STARTUP%\GazeFocus.vbs" (
    del "%STARTUP%\GazeFocus.vbs"
    echo Otomatik baslatma KAPATILDI.
    echo Program artik Windows acilisinda kendiliginden baslamayacak.
    echo ^(Istersen yine baslat.bat ile elle calistirabilirsin.^)
) else (
    echo Zaten otomatik baslatma acik degildi, yapilacak bir sey yok.
)
echo.
pause
