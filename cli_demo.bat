@echo off
REM VLM Tool CLI 使用範例 (Windows)
REM
REM 執行前請確認：
REM   1. Python 環境已安裝 requirements.txt 中的套件
REM   2. 若需要 VLM 功能，請先啟動 LM Studio 並載入視覺模型
REM      預設端點：http://localhost:1234
REM   3. 如需指定不同的 VLM 端點，設定環境變數：
REM      set VLM_BASE_URL=http://localhost:1234/v1
REM      set VLM_MODEL=google/gemma-3-4b-it

echo ========================================
echo  VLM Tool CLI Demo
echo ========================================

REM ── help ──────────────────────────────────────────────────────────────────
echo.
echo [1] 顯示主選單 --help
python cli.py --help

echo.
echo [2] 顯示 analyze 子命令說明
python cli.py analyze --help

echo.
echo [3] 顯示 symbol-check 子命令說明
python cli.py symbol-check --help

echo.
echo [4] 顯示 batch 子命令說明
python cli.py batch --help

echo.
echo [5] 顯示 query 子命令說明
python cli.py query --help

REM ── symbol-check (純 CV，不需 VLM) ─────────────────────────────────────────
echo.
echo ========================================
echo  symbol-check 範例（不需要 LM Studio）
echo ========================================

echo.
echo [6] 列出符號庫所有可用符號
python cli.py symbol-check --list-all

REM 以下範例假設 test.jpg 存在，移除 REM 即可執行
REM echo.
REM echo [7] 檢查 test.jpg 是否含有 weld_v 符號
REM python cli.py symbol-check --images test.jpg --symbol weld_v

REM echo.
REM echo [8] 掃描 test.jpg 所有符號
REM python cli.py symbol-check --images test.jpg

REM ── analyze (純 CV 模式) ──────────────────────────────────────────────────
echo.
echo ========================================
echo  analyze 範例（純 CV 模式，不需要 LM Studio）
echo ========================================

REM 以下範例假設 drawing.jpg 存在，移除 REM 即可執行
REM echo.
REM echo [9] 對 drawing.jpg 執行純 CV 分析（不使用 VLM）
REM python cli.py analyze --image drawing.jpg

REM echo.
REM echo [10] 指定 BOM 並輸出到檔案
REM python cli.py analyze --image drawing.jpg --bom "SUS304, T1.5" --output result.json

REM echo.
REM echo [11] 附上母件圖並啟用 RAG 與 VLM（需 LM Studio）
REM python cli.py analyze --image drawing.jpg --parent parent.jpg --bom "SUS304, T1.5" --rag --vlm

REM ── batch ──────────────────────────────────────────────────────────────────
echo.
echo ========================================
echo  batch 範例
echo ========================================

REM 以下範例假設 drawings\ 資料夾存在，移除 REM 即可執行
REM echo.
REM echo [12] 批次分析整個資料夾（純 CV）
REM python cli.py batch --dir drawings\

REM echo.
REM echo [13] 批次分析並輸出 JSON 報告
REM python cli.py batch --dir drawings\ --output batch_result.json

REM echo.
REM echo [14] 批次分析 + BOM + RAG + VLM（需 LM Studio）
REM python cli.py batch --dir drawings\ --bom "SUS304" --rag --vlm --output batch_result.json

REM ── query ──────────────────────────────────────────────────────────────────
echo.
echo ========================================
echo  query 範例（需要 LM Studio）
echo ========================================

REM 以下範例假設 drawing.jpg 存在且 LM Studio 已啟動，移除 REM 即可執行
REM echo.
REM echo [15] 問 VLM 是非題
REM python cli.py query --image drawing.jpg --ask "這張圖有焊接符號嗎?" --vlm

echo.
echo ========================================
echo  Demo 完成
echo ========================================
pause
