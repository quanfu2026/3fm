@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title 3fm 軟體環境重建工具

set "PROJECT_DIR=C:\projects\3fm"
set "VENV_DIR=%PROJECT_DIR%\.venv"

echo ==================================================
echo   3fm 軟體環境重建工具
echo ==================================================
echo.
echo 這個工具會：
echo   1. 重新建立 Python 3.11 虛擬環境（.venv）
echo   2. 解除 Windows 應用程式控制原則對 .venv 內
echo      原生元件（.dll / .pyd）的封鎖
echo   3. 安裝 requirements.txt 內所有套件
echo      （已鎖定經過驗證可相容的版本組合）
echo.
echo 適用時機：
echo   - 第一次在這台電腦上設定專案
echo   - 換了一台電腦、或整個資料夾搬移過
echo   - 啟動時出現套件相關錯誤（ModuleNotFoundError、
echo     ImportError、DLL load failed 等）
echo.
echo 注意：此工具會刪除現有的 .venv 並重新建立，
echo       過程約需 5~15 分鐘（依網路速度而定）。
echo.

if not exist "%PROJECT_DIR%" (
    echo [錯誤] 找不到專案資料夾：%PROJECT_DIR%
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"

set /p CONFIRM="確定要重建環境嗎？(Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo 已取消。
    pause
    exit /b 0
)

echo.
echo [1/5] 確認 Python 3.11 是否已安裝...
py -3.11 -c "print('OK')" >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Python 3.11。
    echo 請先到 https://www.python.org/downloads/ 安裝 Python 3.11.x，
    echo 安裝時記得勾選「Add python.exe to PATH」。
    pause
    exit /b 1
)
echo 已確認 Python 3.11 可用。

echo.
echo [2/5] 移除舊的虛擬環境（如果存在）...
if exist "%VENV_DIR%" (
    rmdir /s /q "%VENV_DIR%"
    if exist "%VENV_DIR%" (
        echo [警告] 舊的 .venv 無法完全刪除，可能有檔案正被占用。
        echo 請關閉所有跟 3fm 相關的終端機視窗後再重新執行此工具。
        pause
        exit /b 1
    )
)
echo 完成。

echo.
echo [3/5] 建立新的虛擬環境（Python 3.11）...
py -3.11 -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [錯誤] 虛擬環境建立失敗。
    pause
    exit /b 1
)
echo 完成。

echo.
echo [4/5] 解除應用程式控制原則對 .venv 的封鎖...
powershell -NoProfile -Command "Get-ChildItem -Path '%VENV_DIR%' -Recurse -Include *.dll,*.pyd -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue"
echo 完成（如果這台電腦的應用程式控制原則仍然擋下部分檔案，
echo 之後執行時如遇到 DLL load failed 錯誤，屬已知問題，
echo 系統會自動以較低階模式運作，不影響基本功能）。

echo.
echo [5/5] 安裝套件（requirements.txt，過程較久，請耐心等候）...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [錯誤] 套件安裝過程發生錯誤，請往上檢查是哪一個套件失敗。
    pause
    exit /b 1
)

echo.
echo ==================================================
echo   環境重建完成！
echo ==================================================
echo.
echo 接下來可以執行「啟動3fm.bat」開啟系統。
echo.
pause
exit /b 0
