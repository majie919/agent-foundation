from contextlib import asynccontextmanager

from fastapi import FastAPI

import config
import db
from routers import greeting, products, system


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
)

app.include_router(system.router)
app.include_router(greeting.router)
app.include_router(products.router)
