@echo off
chcp 65001 >nul
title 3FM RAG Demo

echo ============================================================
echo   3FM RAG Pipeline - 一鍵啟動
echo ============================================================
echo.

:: 切換到專案目錄（自動偵測 script 所在位置）
cd /d "%~dp0"

:: 啟動 venv
if exist "venv\Scripts\activate.bat" (
    echo [1] 啟動虛擬環境...
    call venv\Scripts\activate.bat
) else (
    echo [警告] 找不到 venv，使用系統 Python
)

:: 檢查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Python，請先安裝 Python 3.11
    pause
    exit /b 1
)

:: 安裝缺少的套件（快速檢查）
echo [2] 檢查套件...
python -c "import jieba, rank_bm25, sentence_transformers" >nul 2>&1
if errorlevel 1 (
    echo [3] 安裝缺少套件...
    pip install jieba rank-bm25 sentence-transformers FlagEmbedding python-dotenv -q
    echo 套件安裝完成
)

:: 執行 Demo
echo.
echo [4] 啟動 RAG Demo...
echo ============================================================
echo.

if "%1"=="-i" (
    python demo_rag.py --interactive
) else if "%1"=="--interactive" (
    python demo_rag.py --interactive
) else if "%1"=="--rebuild" (
    python demo_rag.py --rebuild
) else (
    python demo_rag.py
)

echo.
echo ============================================================
echo   完成
echo ============================================================
pause