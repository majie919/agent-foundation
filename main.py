from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

import config
import db
from routers import greeting, products, system

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时建表，关闭时什么都不用做。

    为什么不在模块顶层直接调 init_db()：import 阶段就写文件是隐式副作用，
    测试里一 import 就会建库，很难控制。放在 lifespan 里，启动才建。
    """
    db.init_db()
    yield


app = FastAPI(
    title="agent-foundation",
    version=config.APP_VERSION,
    description="AI 应用实习准备项目：从接口拆分开始，逐步长成一个能跑批处理的小工具。",
    lifespan=lifespan,
    # 关掉默认文档页：它从国外 CDN 加载 swagger-ui，网络不通时整页白板
    docs_url=None,
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/docs", include_in_schema=False)
def swagger_ui():
    """文档页改用本地静态资源。

    FastAPI 默认的 /docs 会去 cdn.jsdelivr.net 取 swagger-ui 的 css 和 js。
    国内网络经常连不上，页面就变成白板——看着像"代码坏了"。
    把这两个文件放进 static/swagger 后，断网也能打开文档。
    """
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_css_url="/static/swagger/swagger-ui.css",
        swagger_js_url="/static/swagger/swagger-ui-bundle.js",
    )


app.include_router(system.router)
app.include_router(greeting.router)
app.include_router(products.router)
