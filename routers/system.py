from fastapi import APIRouter

from models import HealthResponse, VersionResponse


router = APIRouter(tags=["系统"])


@router.get("/health", response_model=HealthResponse, summary="健康检查")
def health():
    return {"ok": True, "service": "agent-foundation", "version": "0.2.0"}


@router.get("/version", response_model=VersionResponse, summary="版本信息")
def version():
    return {"version": "0.2.0", "build_time": "2026-11-10 18:40"}
