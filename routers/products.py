"""产品文案接口：单条生成 + 批量生成。"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException, Query

import config
from llm import generate_listing
from models import (
    BatchItemResult,
    BatchSummary,
    ProductBatchIn,
    ProductBatchOut,
    ProductDescription,
    ProductIn,
)

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


def describe_one(payload: ProductIn, mode: str) -> dict:
    """生成单条文案。失败时抛异常，由调用方决定怎么处理。

    单条接口：转成 502 返回给客户端。
    批量接口：只把这一条标记为失败，其余继续跑。
    """
    if mode == "mock":
        data = build_mock_listing(payload)
        source = "mock"
    else:
        data = generate_listing(payload.name, payload.category, payload.features)
        source = "llm"

    title = trim_title(data["title"])

    return {
        "title": title,
        "bullets": data["bullets"],
        "keywords": data["keywords"],
        "char_count": len(title),
        "source": source,
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
    try:
        return describe_one(payload, mode)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"文案生成失败：{e}") from e


@router.post(
    "/batch",
    response_model=ProductBatchOut,
    summary="批量生成 listing 文案（最多 20 条）",
)
def describe_products_batch(
    payload: ProductBatchIn,
    mode: str = Query(
        default="llm",
        pattern="^(llm|mock)$",
        description="llm 调用真实模型；mock 用模板拼接，便于对比",
    ),
    workers: int = Query(
        default=4,
        ge=1,
        le=8,
        description="并发数。越大越快，但可能触发模型接口限流",
    ),
):
    # 先检查 Key：不然后面 20 条各自失败一遍，既慢又看不出真正原因
    if mode == "llm":
        try:
            config.require_api_key()
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=f"未配置 API Key：{e}") from e

    start = time.perf_counter()
    results: list[BatchItemResult | None] = [None] * len(payload.items)

    def work(index: int, item: ProductIn) -> BatchItemResult:
        try:
            listing = describe_one(item, mode)
            return BatchItemResult(index=index, name=item.name, ok=True, listing=listing)
        except Exception as e:  # 单条失败不影响整批
            return BatchItemResult(index=index, name=item.name, ok=False, error=str(e))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, i, item) for i, item in enumerate(payload.items)]
        for future in as_completed(futures):
            result = future.result()
            results[result.index] = result

    elapsed = time.perf_counter() - start
    final_results = [r for r in results if r is not None]
    success = sum(1 for r in final_results if r.ok)

    return {
        "results": final_results,
        "summary": BatchSummary(
            total=len(payload.items),
            success=success,
            failed=len(final_results) - success,
            elapsed_seconds=round(elapsed, 2),
        ),
        "source": "mock" if mode == "mock" else "llm",
    }
