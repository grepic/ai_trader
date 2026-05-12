"""Report endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.core import DailyReport
from app.schemas.core import DailyReportOut

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/daily", response_model=list[DailyReportOut])
async def list_daily_reports(db: DbSession, limit: int = 30):
    result = await db.execute(
        select(DailyReport).order_by(DailyReport.report_date.desc()).limit(limit)
    )
    return [DailyReportOut.model_validate(r) for r in result.scalars().all()]


@router.get("/daily/{report_date}", response_model=DailyReportOut)
async def get_daily_report(report_date: str, db: DbSession):
    result = await db.execute(
        select(DailyReport).where(DailyReport.report_date == report_date)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail=f"No report for {report_date}")
    return DailyReportOut.model_validate(report)
