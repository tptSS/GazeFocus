@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "PROJDIR=%~dp0"
if "%PROJDIR:~-1%"=="\" set "PROJDIR=%PROJDIR:~0,-1%"

if not exist "%PROJDIR%\.venv\Scripts\python.exe" (
    echo Once programi normal sekilde ^(baslat.bat ile^) bir kez calistirip
    echo kurulumu ve kalibrasyonu tamamlamalisin, sonra bunu calistir.
    pause
    exit /b 1
)
if not exist "%APPDATA%\GazeFocus\calibration.json" (
    echo Henuz kalibrasyon yapilmamis. Otomatik baslatma acilirsa her
    echo acilista sessizce kalibrasyon ekrani acilir, bu kafa karistirir.
    echo Once baslat.bat ile bir kez calistirip kalibrasyonu tamamla,
    echo sonra bu dosyayi tekrar calistir.
    pause
    exit /b 1
)

rem Asil calisma dosyasi: pencere/duraklama yok, her sey log dosyasina yazilir.
> "%PROJDIR%\_oto_calistir.bat" (
    echo @echo off
    echo cd /d "%PROJDIR%"
    echo if not exist "%%APPDATA%%\GazeFocus" mkdir "%%APPDATA%%\GazeFocus"
    echo echo ---- %%date%% %%time%% baslatildi ---- ^>^> "%%APPDATA%%\GazeFocus\baslat.log"
    echo ".venv\Scripts\python.exe" gaze_focus.py ^>^> "%%APPDATA%%\GazeFocus\baslat.log" 2^>^&1
)

rem Windows acilisinda bu dosyayi pencere gostermeden calistiracak kisa bir vbs.
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
> "%STARTUP%\GazeFocus.vbs" (
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo WshShell.Run """%PROJDIR%\_oto_calistir.bat""", 0, False
)

echo.
echo Otomatik baslatma ACILDI.
echo Bundan sonra bilgisayarini her actiginda GazeFocus kendiliginden,
echo gizli/gorunmez sekilde arka planda baslayacak - hicbir sey yapmana gerek yok.
echo.
echo Sorun olursa log dosyasina bakabilirsin: %%APPDATA%%\GazeFocus\baslat.log
echo Otomatik baslatmayi kapatmak icin: otomatik_baslatmayi_kapat.bat
echo.
pause
