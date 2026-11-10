from fastapi import APIRouter

from models import GreetingRequest, GreetingResponse

router = APIRouter(tags=["打招呼"])

TEMPLATES = {"zh": "你好，{name}", "en": "hello, {name}"}


@router.get("/hello/{name}", response_model=GreetingResponse, summary="路径参数打招呼")
def hello_by_path(name: str):
    print(f">>> hello_by_path 命中，name={name}，类型={type(name).__name__}")
    return {"message": f"你好，{name}", "name": name, "lang": "zh"}


@router.post("/hello", response_model=GreetingResponse, summary="请求体打招呼")
def hello_by_body(payload: GreetingRequest):
    print(f">>> hello_by_body 命中，收到 {payload.model_dump()}")
    return {
        "message": TEMPLATES[payload.lang].format(name=payload.name),
        "name": payload.name,
        "lang": payload.lang,
    }
