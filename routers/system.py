from fastapi import APIRouter

import config
from models import HealthResponse, VersionResponse


router = APIRouter(tags=["系统"])


@router.get("/health", response_model=HealthResponse, summary="健康检查")
def health():
    return {"ok": True, "service": "agent-foundation", "version": config.APP_VERSION}


@router.get("/version", response_model=VersionResponse, summary="版本信息")
def version():
    return {"version": config.APP_VERSION, "build_time": config.BUILD_TIME}
