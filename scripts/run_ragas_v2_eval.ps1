# RAGAS V2 evaluation using NVIDIA NIM judge
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

$Dataset = Join-Path $Root "eval_baseline.jsonl"
if (-not (Test-Path $Dataset)) {
    Write-Host "ERROR: dataset not found: $Dataset" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Starting RAGAS V2 evaluation..." -ForegroundColor Cyan
Write-Host "  Dataset: eval_baseline.jsonl"
Write-Host "  Judge:   https://integrate.api.nvidia.com/v1"
Write-Host "  Model:   nvidia/nemotron-3-super-120b-a12b" -ForegroundColor Yellow
Write-Host ""

& $Py scripts\ragas_v2_eval.py evaluate `
    --dataset eval_baseline.jsonl `
    --out results\ragas_v2_result.csv `
    --judge-base-url https://integrate.api.nvidia.com/v1 `
    --judge-model nvidia/nemotron-3-super-120b-a12b `
    --judge-api-key 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

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Evaluation finished." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Evaluation FAILED with exit code $LASTEXITCODE" -ForegroundColor Red
}

Read-Host "Press Enter to exit"