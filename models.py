from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    ok: bool = Field(description="服务是否正常")
    service: str = Field(description="服务名")
    version: str = Field(description="当前版本号")


class GreetingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=20, description="要打招呼的人名")
    lang: str = Field(default="zh", pattern="^(zh|en)$", description="语言，只能是 zh 或 en")


class GreetingResponse(BaseModel):
    message: str = Field(description="打招呼的内容")
    name: str = Field(description="回显的人名")
    lang: str = Field(description="实际使用的语言")


class VersionResponse(BaseModel):
    version: str = Field(description="当前服务版本号，格式 x.y.z")
    build_time: str = Field(description="构建时间，格式 YYYY-MM-DD HH:MM")


class ProductIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Bamboo Cutting Board",
                "category": "kitchen",
                "features": ["eco friendly", "easy to clean", "gift ready"],
            }
        }
    )

    name: str = Field(min_length=1, max_length=100, description="产品英文名，例如 Bamboo Cutting Board")
    category: str = Field(min_length=1, max_length=30, description="类目，例如 kitchen / toy / beauty")
    features: list[str] = Field(min_length=1, max_length=5, description="卖点列表，1 到 5 条")


class ProductDescription(BaseModel):
    title: str = Field(description="listing 标题")
    bullets: list[str] = Field(description="五点描述，逐条列出卖点")
    keywords: list[str] = Field(description="搜索关键词")
    char_count: int = Field(description="标题字符数，亚马逊标题上限 200")
    source: str = Field(description="文案来源：mock 表示模板生成，llm 表示大模型生成")


class ProductBatchIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {"name": "Bamboo Cutting Board", "category": "kitchen", "features": ["eco friendly", "easy to clean"]},
                    {"name": "Silicone Baking Mat", "category": "kitchen", "features": ["non stick", "reusable", "dishwasher safe"]},
                    {"name": "LED Desk Lamp", "category": "home", "features": ["dimmable", "usb charging"]},
                ]
            }
        }
    )

    items: list[ProductIn] = Field(min_length=1, max_length=20, description="产品列表，1 到 20 条")


class BatchItemResult(BaseModel):
    index: int = Field(description="该产品在请求列表中的位置，从 0 开始")
    name: str = Field(description="产品名，方便对账")
    ok: bool = Field(description="这一条是否成功")
    listing: ProductDescription | None = Field(default=None, description="成功时的文案，失败时为 null")
    error: str | None = Field(default=None, description="失败原因，成功时为 null")


class BatchSummary(BaseModel):
    total: int = Field(description="提交的产品总数")
    success: int = Field(description="成功条数")
    failed: int = Field(description="失败条数")
    elapsed_seconds: float = Field(description="整批耗时（秒）")


class ProductBatchOut(BaseModel):
    results: list[BatchItemResult] = Field(description="每条产品的处理结果，顺序与请求一致")
    summary: BatchSummary = Field(description="整批统计")
    source: str = Field(description="文案来源：mock 或 llm")
