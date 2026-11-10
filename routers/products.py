from fastapi import APIRouter

from models import ProductDescription, ProductIn

router = APIRouter(prefix="/products", tags=["产品文案"])


@router.post("/describe", response_model=ProductDescription, summary="根据产品信息生成 listing 文案")
def describe_product(payload: ProductIn):
    title = f"{payload.name} - {payload.category.title()} Essential"

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
        "source": "mock",
    }
