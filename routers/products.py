from fastapi import APIRouter, HTTPException, Query

from llm import generate_listing
from models import ProductDescription, ProductIn

router = APIRouter(prefix="/products", tags=["产品文案"])

TITLE_LIMIT = 200


def trim_title(text: str, limit: int = TITLE_LIMIT) -> str:
    """标题超长时截断到 limit 以内，且不把单词切成两半。"""
    if len(text) <= limit:
        return text

    if text[limit].isspace():
        return text[:limit].rstrip(" ,-")

    cut = text[:limit]
    last_space = cut.rfind(" ")
    if last_space > 0:
        cut = cut[:last_space]

    return cut.rstrip(" ,-")


def build_mock_listing(payload: ProductIn) -> dict:
    """模板版本，不调模型。用于对比效果，也方便没配 Key 时联调。"""
    bullets = []
    for i, feature in enumerate(payload.features, start=1):
        bullets.append(f"{i}. {feature}")

    keywords = [payload.category, payload.name.lower()]
    for feature in payload.features[:3]:
        keywords.append(feature.lower())

    return {
        "title": f"{payload.name} - {payload.category.title()} Essential",
        "bullets": bullets,
        "keywords": keywords,
    }


@router.post(
    "/describe",
    response_model=ProductDescription,
    summary="根据产品信息生成 listing 文案",
)
def describe_product(
    payload: ProductIn,
    mode: str = Query(
        default="llm",
        pattern="^(llm|mock)$",
        description="llm 调用真实模型；mock 用模板拼接，便于对比",
    ),
):
    if mode == "mock":
        data = build_mock_listing(payload)
        source = "mock"
    else:
        try:
            data = generate_listing(payload.name, payload.category, payload.features)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"文案生成失败：{e}") from e
        source = "llm"

    title = trim_title(data["title"])

    return {
        "title": title,
        "bullets": data["bullets"],
        "keywords": data["keywords"],
        "char_count": len(title),
        "source": source,
    }
