from fastapi import FastAPI

from routers import greeting, products, system

app = FastAPI(
    title="agent-foundation",
    version="0.3.0",
    description="AI 应用实习准备项目：从接口拆分开始，逐步长成一个能跑批处理的小工具。",
)

app.include_router(system.router)
app.include_router(greeting.router)
app.include_router(products.router)
