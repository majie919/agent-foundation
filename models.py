from pydantic import BaseModel, Field


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
    version: str = Field(description="这里换成你写的中文说明")
    build_time: str = Field(description="这里换成你写的中文说明")
