@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul

if not exist .venv (
    echo Sanal ortam olusturuluyor...
    set PYEXE=
    for %%V in (3.12 3.11 3.10) do (
        if "!PYEXE!"=="" (
            py -%%V -c "exit()" >nul 2>&1
            if not errorlevel 1 set PYEXE=py -%%V
        )
    )
    if "!PYEXE!"=="" (
        echo Uyumlu Python bulunamadi [3.10-3.12 gerekli; mediapipe 3.13'te calismiyor].
        echo "https://www.python.org/downloads/" adresinden Python 3.12 kurup tekrar deneyin.
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
