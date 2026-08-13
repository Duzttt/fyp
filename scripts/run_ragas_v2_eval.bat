@echo off
setlocal
REM RAGAS V2 evaluation using NVIDIA NIM judge
cd /d "%~dp0\.."

set PYTHON=.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

"%PYTHON%" scripts\ragas_v2_eval.py evaluate ^
    --dataset eval_baseline.jsonl ^
    --out results\ragas_v2_result.csv ^
    --judge-base-url https://integrate.api.nvidia.com/v1 ^
    --judge-model nvidia/nemotron-3-super-120b-a12b ^
    --judge-api-key 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

echo.
echo Done. Press any key to close.
pause >nul
endlocal