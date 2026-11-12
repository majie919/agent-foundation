"""接入方鉴权与限流。

两个依赖都写成 FastAPI 的依赖函数，路由通过 Depends 注入：
- require_client_key：校验 X-API-Key 请求头，返回调用方标识
- rate_limit：依赖上一个的结果，做滑动窗口限流

依赖链（先验身份，再计数）的好处：限流天然按"调用方"分组，
将来要给不同 Key 不同的配额，只需要在这里改，路由代码一行不动。

为什么挂在 router 级的 dependencies 上而不是每个接口各写一遍：
同一组接口共享同一套规则，逐个写在装饰器里迟早会漏一个；
挂在 router 上，以后新增接口自动继承。
"""

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, Header, HTTPException

import config


def require_client_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """校验调用方身份，返回用于限流计数的 key。

    - 未配置 API_KEYS：开发模式直接放行，否则本地连自己都调不了
    - 缺头和头不对都返回 401。401 是"身份没通过"；
      403 是"身份对但没权限"，语义不同，别混用
    """
    if not config.API_KEYS:
        return "dev"
    if not x_api_key:
        raise HTTPException(status_code=401, detail="缺少请求头 X-API-Key")
    if x_api_key not in config.API_KEYS:
        raise HTTPException(status_code=401, detail="API Key 无效")
    return x_api_key


class SlidingWindowLimiter:
    """滑动窗口限流：只看"最近 window 秒"内的请求次数。

    为什么不用固定窗口（每分钟清零计数器）：
    固定窗口在边界处会放进双倍流量——第 59 秒打满 30 次，
    第 61 秒计数器清零又能打 30 次，实际一分钟内放过 60 次。
    滑动窗口记录每次请求的时间戳，永远只统计最近 N 秒，没有这个洞。
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        # FastAPI 的同步端点跑在线程池里，这个字典会被多个线程同时读写
        self._lock = threading.Lock()

    def hit(self, key: str) -> int:
        """记录一次请求。超限返回应等待的秒数，正常返回 0。"""
        now = time.monotonic()  # 单调时钟：不受系统改时间影响
        with self._lock:
            q = self._hits[key]
            cutoff = now - self.window
            while q and q[0] <= cutoff:
                q.popleft()  # 只弹过期的时间戳，内存不随时间增长
            if len(q) >= self.max:
                # 最早那次请求出窗的时刻，就是下一个名额释放的时刻
                retry_after = math.ceil(q[0] + self.window - now)
                return max(retry_after, 1)
            q.append(now)
            return 0


_limiter = SlidingWindowLimiter(config.RATE_LIMIT_MAX, config.RATE_LIMIT_WINDOW)


def rate_limit(client_key: str = Depends(require_client_key)) -> None:
    """限流依赖。超限抛 429，并带上 Retry-After 响应头。

    Retry-After 是 HTTP 标准头：告诉客户端"等 N 秒再试"。
    这和 llm.py 处理 429 的逻辑是同一个协议的两端——
    服务端告诉客户端等多久，客户端的重试就该照着等。
    """
    retry_after = _limiter.hit(client_key)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail=(
                f"请求过于频繁：{config.RATE_LIMIT_WINDOW} 秒内最多 "
                f"{config.RATE_LIMIT_MAX} 次，请 {retry_after} 秒后重试"
            ),
            headers={"Retry-After": str(retry_after)},
        )
