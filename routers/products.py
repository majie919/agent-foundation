"""产品文案接口：单条生成 + 批量生成。"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException, Query

import config
import db
from llm import generate_listing
from models import (
    BatchItemResult,
    BatchSummary,
    HistoryOut,
    ProductBatchIn,
    ProductBatchOut,
    ProductDescription,
    ProductIn,
)
from security import rate_limit

# 鉴权 + 限流挂在 router 级：本组所有接口（含将来新增的）自动继承，
# 不用在每个装饰器上重复写。/health /version 这类探测接口不在这里，保持公开。
router = APIRouter(prefix="/products", tags=["产品文案"], dependencies=[Depends(rate_limit)])

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


def _save_quietly(pairs: list[tuple[dict, dict]]) -> None:
    """落库是旁路：存档失败只记一笔，不影响已经生成好的结果。

    这里和"失败不降级"是两回事，方向要分清：
    - 生成失败必须报错，因为用户拿不到想要的东西；
    - 存档失败只影响我们自己回溯，用户的东西已经给了。
    判断标准是"失败影响的是谁"。
    """
    if not pairs:
        return
    try:
        db.save_many(pairs)
    except Exception as e:
        print(f"[warn] 落库失败，本次 {len(pairs)} 条未存档：{e}")


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
        listing = describe_one(payload, mode)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"文案生成失败：{e}") from e

    # 落库放在 try 外面：文案已经生成好了，不能因为存档失败让用户重跑一次
    _save_quietly([(payload.model_dump(), listing)])
    return listing


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

    # 只存成功的：失败条目没有 listing，硬塞进去会破坏表结构
    _save_quietly([
        (payload.items[r.index].model_dump(), r.listing.model_dump())
        for r in final_results
        if r.ok and r.listing is not None
    ])

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


@router.get(
    "/history",
    response_model=HistoryOut,
    summary="查看历史生成记录（最新在前）",
)
def get_history(
    limit: int = Query(default=10, ge=1, le=100, description="返回条数上限"),
    source: str | None = Query(
        default=None,
        pattern="^(mock|llm)$",
        description="只看某个来源，不传则全部",
    ),
):
    items = db.list_history(limit=limit, source=source)
    # total 是总数，不受 limit 影响：前端要靠它算"还有多少页"
    return {"total": db.count(source), "limit": limit, "items": items}
