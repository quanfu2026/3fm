@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title 3fm 電商智能客服系統啟動器

set "PROJECT_DIR=C:\projects\3fm"
set "PYTHON_EXE=%PROJECT_DIR%\.venv\Scripts\python.exe"
set "RUN_FILE=%PROJECT_DIR%\run_web.py"
set "WEB_URL=http://127.0.0.1:5000"

echo ==================================================
echo   3fm 電商智能客服系統 - 一鍵啟動
echo ==================================================
echo.

if not exist "%PROJECT_DIR%" (
    echo [錯誤] 找不到專案資料夾：
    echo %PROJECT_DIR%
    echo.
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo [提示] 找不到虛擬環境 Python：
    echo %PYTHON_EXE%
    echo.
    echo 這通常代表軟體環境還沒建立，或是換了一台電腦、
    echo 資料夾被搬移過。
    echo.
    set /p DOREBUILD="要現在執行「重建環境3fm.bat」自動設定嗎？(Y/N): "
    if /i "!DOREBUILD!"=="Y" (
        if exist "%PROJECT_DIR%\重建環境3fm.bat" (
            call "%PROJECT_DIR%\重建環境3fm.bat"
            if not exist "%PYTHON_EXE%" (
                echo [錯誤] 環境重建後仍找不到 Python，請檢查上方錯誤訊息。
                pause
                exit /b 1
            )
        ) else (
            echo [錯誤] 找不到重建工具：%PROJECT_DIR%\重建環境3fm.bat
            pause
            exit /b 1
        )
    ) else (
        echo 已取消啟動。請手動執行「重建環境3fm.bat」後再試一次。
        pause
        exit /b 1
    )
)

if not exist "%RUN_FILE%" (
    echo [錯誤] 找不到啟動檔：
    echo %RUN_FILE%
    echo.
    pause
    exit /b 1
)

echo [1/4] 檢查 Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
    echo [警告] 找不到 Ollama 指令。
    echo 系統仍會啟動 Flask，但 AI 回答可能無法使用。
) else (
    tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
    if errorlevel 1 (
        echo 啟動 Ollama 服務...
        start "Ollama Server" /min cmd /c "ollama serve"
        timeout /t 3 /nobreak >nul
    ) else (
        echo Ollama 已在執行。
    )
)

echo.
echo [2/4] 切換到專案資料夾...
cd /d "%PROJECT_DIR%"

echo.
echo [3/4] 啟動 Flask 網站...
start "3fm Flask Server" cmd /k ""%PYTHON_EXE%" "%RUN_FILE%""

echo.
echo [4/4] 等待網站啟動並開啟瀏覽器...
timeout /t 5 /nobreak >nul
start "" "%WEB_URL%"

echo.
echo 3fm 已啟動：
echo %WEB_URL%
echo.
echo 請勿關閉「3fm Flask Server」視窗。
timeout /t 3 /nobreak >nul
exit /b 0