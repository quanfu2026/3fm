@echo off
REM ════════════════════════════════════════════════════════
REM  RAG 評測系統 — 一鍵啟動腳本
REM  執行前請確認：
REM    1. LM Studio 已開啟並載入 Qwen2.5 模型
REM    2. product_specs.txt 已存在（先執行 build_knowledge_base_multi.py）
REM ════════════════════════════════════════════════════════

echo ========================================
echo  RAG 自動化評測系統
echo ========================================

REM 啟動虛擬環境（如果有的話）
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM 安裝必要套件
echo [1/3] 安裝必要套件...
pip install rank-bm25 jieba sentence-transformers openai python-docx tqdm -q

REM Step 1：建立知識庫（如果 product_specs.txt 不存在）
if not exist "knowledge_base\docs\product_specs.txt" (
    echo [2/3] 建立知識庫課本...
    python build_knowledge_base_multi.py
) else (
    echo [2/3] 知識庫已存在，跳過建立
)

REM Step 2：執行評測
echo [3/3] 開始自動化評測...
echo.

REM 選擇執行模式
REM 完整四組對照（需要 LM Studio 在線）：
REM python run_experiments.py

REM 單組快速測試（僅評估檢索指標，不需 LLM）：
python test_rag_from_word.py --skip-llm --max-q 20

echo.
echo ✅  評測完成！結果在 evaluation_results\ 資料夾
pause
