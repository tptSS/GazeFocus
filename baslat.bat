@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul

if not exist .venv (
    echo Sanal ortam olusturuluyor...

    call :find_python
    if "!PYEXE!"=="" (
        echo Uyumlu Python bulunamadi [3.10-3.12 gerekli; mediapipe 3.13'te calismiyor].
        echo Otomatik kurulum deneniyor, internet gerekiyor...
        call :install_python
        call :find_python
    )
    if "!PYEXE!"=="" (
        echo.
        echo Python otomatik kurulamadi.
        echo Lutfen https://www.python.org/downloads/ adresinden Python 3.12 kurun
        echo ^(kurulum ekraninda "Add python.exe to PATH" kutusunu isaretleyin^)
        echo ve bu dosyayi tekrar calistirin.
        pause
        exit /b 1
    )

    echo Kullanilan: !PYEXE!
    !PYEXE! -m venv .venv
    if errorlevel 1 (
        echo Sanal ortam olusturulamadi.
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Bagimliliklar kurulamadi, .venv klasorunu silip tekrar deneyin.
        pause
        exit /b 1
    )
) else (
    call .venv\Scripts\activate.bat
)

python gaze_focus.py %*
pause
exit /b 0

:find_python
set PYEXE=
for %%V in (3.12 3.11 3.10) do (
    if "!PYEXE!"=="" (
        py -%%V -c "exit()" >nul 2>&1
        if not errorlevel 1 set PYEXE=py -%%V
    )
)
exit /b 0

:install_python
rem 1) Once winget dene (Windows 10/11'de hazir gelir, UAC istemeden kurar)
where winget >nul 2>&1
if not errorlevel 1 (
    echo winget ile Python 3.12 kuruluyor, birkac dakika surebilir...
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
)

call :find_python
if not "!PYEXE!"=="" exit /b 0

rem 2) winget yoksa/basarisizsa python.org'dan dogrudan indirip sessiz kur
where curl >nul 2>&1
if errorlevel 1 (
    echo curl bulunamadi, otomatik indirme yapilamiyor.
    exit /b 1
)
echo python.org'dan Python 3.12 indiriliyor...
set "PYINST=%TEMP%\gazefocus_python_installer.exe"
curl.exe -L --fail -o "%PYINST%" "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
if errorlevel 1 (
    echo Indirme basarisiz oldu.
    exit /b 1
)
echo Python kuruluyor ^(arka planda, pencere acilmayabilir, bekleyin^)...
"%PYINST%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1
del "%PYINST%" >nul 2>&1
exit /b 0
