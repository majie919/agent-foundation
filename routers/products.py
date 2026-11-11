from fastapi import APIRouter

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


@router.post("/describe", response_model=ProductDescription, summary="根据产品信息生成 listing 文案")
def describe_product(payload: ProductIn):
    title = trim_title(f"{payload.name} - {payload.category.title()} Essential")

    bullets = []
    for i, feature in enumerate(payload.features, start=1):
        bullets.append(f"{i}. {feature}")

    keywords = [payload.category, payload.name.lower()]
    for feature in payload.features[:3]:
        keywords.append(feature.lower())

    return {
        "title": title,
        "bullets": bullets,
        "keywords": keywords,
        "char_count": len(title),
        "source": "mock",
    }
