from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException

from ..finance import build_financial_report, _month_number, _month_string
from ..reasoning import JAVA_VERSION, analyze, diagnose_finance
from ..schemas import AnalyzeRequest, FinancialReportRequest

router = APIRouter(prefix="/api/kbr", tags=["Knowledge-Based Reasoning (OWL/Pellet)"])


@router.get("/status")
def kbr_engine_status() -> dict[str, Any]:
    """Mengecek status engine OWL 2 DL / SWRL Pellet Reasoner."""
    return {
        "ok": True,
        "engine": "OWL + SWRL / Pellet",
        "java": JAVA_VERSION,
        "mode": "Decoupled Asynchronous Reasoner",
    }


@router.post("/diagnose")
def run_kbr_diagnosis(request: FinancialReportRequest) -> dict[str, Any]:
    """Menjalankan penalaran berbasis ontologi OWL 2 DL dan aturan SWRL via Pellet Reasoner.
    
    Terisolasi dari endpoint Dashboard/Reports agar beban komputasi ontologi Java (~1.5s)
    hanya dijalankan saat dibutuhkan tanpa memperlambat interaksi umum aplikasi.
    """
    try:
        data = build_financial_report(request.workspace, request.month)
        curr_m_num = _month_number(request.month)
        prev_m_str = _month_string(curr_m_num - 1)
        prev_data = None
        try:
            prev_rows = [tx for tx in request.workspace.transactions if tx.date.strftime("%Y-%m") == prev_m_str]
            if prev_rows:
                prev_data = build_financial_report(request.workspace, prev_m_str)
        except Exception:
            prev_data = None

        diagnosis = diagnose_finance(
            data["report"],
            previous_report=prev_data["report"] if prev_data else None,
        )
        diagnosis["period"] = request.month
        return diagnosis
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/analyze")
def run_generic_analysis(request: AnalyzeRequest) -> dict[str, Any]:
    """Analisis indikator generik via reasoner."""
    try:
        return analyze(request.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
