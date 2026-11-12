"""调用 DeepSeek 生成 listing 文案。

对外只有两个函数：
- clean_text()        清洗模型输出里的排版字符
- generate_listing()  生成标题 / 五点 / 关键词
"""

import json
import random
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable

import config

# 模型爱输出"排版正确"的字符，电商平台和数据库只认 ASCII
_PUNCT_MAP = str.maketrans(
    {
        "\u2013": "-",    # – en dash
        "\u2014": "-",    # — em dash
        "\u2212": "-",    # − 减号
        "\u2018": "'",    # ‘
        "\u2019": "'",    # ’
        "\u201c": '"',    # “
        "\u201d": '"',    # ”
        "\u2026": "...",  # …
        "\u00a0": " ",    # 不间断空格
    }
)

_PROMPT_TEMPLATE = """你是亚马逊 listing 文案专家。根据产品信息生成文案。

产品名：{name}
类目：{category}
卖点：{features}

要求：
1. title：英文标题，50-180 字符，卖点自然融入，不堆砌关键词
2. bullets：5 条英文卖点描述，每条一句话，不加序号
3. keywords：8-12 个英文搜索关键词，全部小写
4. 所有标点只用 ASCII 字符：用 - 而不是长破折号，用直引号而不是弯引号
5. 只输出 JSON，不要 markdown 代码块，不要任何解释

输出格式：
{{"title": "...", "bullets": ["...", "..."], "keywords": ["...", "..."]}}"""

# 这些状态码代表"暂时性故障"，再试一次可能就好了
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class ModelError(RuntimeError):
    """模型调用失败。

    status     HTTP 状态码，网络层失败时为 None
    retryable  是否值得重试（区分"暂时性故障"和"我的请求本身有问题"）
    retry_after 服务端在 Retry-After 头里要求的等待秒数
    """

    def __init__(
        self,
        message: str,
        status: int | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after


def _retry_after_seconds(headers) -> float | None:
    """读取 429 响应里的 Retry-After（只认秒数，HTTP 日期格式先不处理）。"""
    if not headers:
        return None
    raw = headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


def clean_text(text: str) -> str:
    """统一标点，并合并多余空白。"""
    text = str(text).translate(_PUNCT_MAP)
    return " ".join(text.split())


def _call_model(prompt: str, timeout: float = 30.0) -> str:
    """发一次请求，返回模型输出的原始文本。"""
    key = config.require_api_key()

    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        config.DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_bytes = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:200]
        raise ModelError(
            f"模型接口返回 {e.code}：{detail}",
            status=e.code,
            retryable=e.code in _RETRYABLE_STATUS,
            retry_after=_retry_after_seconds(e.headers),
        ) from e
    except urllib.error.URLError as e:
        # 断网、DNS 失败、连接被拒：等一会儿再试有意义
        raise ModelError(f"连不上模型接口：{e.reason}", retryable=True) from e
    except OSError as e:
        # 读超时、连接被重置
        raise ModelError(f"网络异常：{e}", retryable=True) from e

    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ModelError(f"响应不是合法 JSON：{raw_bytes[:120]!r}", retryable=True) from e

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ModelError(f"模型返回格式异常：{str(data)[:200]}", retryable=True) from e


def _extract_json(text: str) -> dict:
    """从模型输出里抠出 JSON，容忍代码块包裹和前后废话。"""
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"返回里找不到 JSON：{text[:150]}")

    return json.loads(cleaned[start : end + 1])


def _parse_listing(raw: str) -> dict:
    """把模型输出的原始文本整理成结构化结果。

    这里所有失败都归为"可重试"——模型每次输出都不一样，换一次很可能就正常了。
    """
    try:
        data = _extract_json(raw)
    except ValueError as e:
        raise ModelError(f"模型输出不是 JSON：{e}", retryable=True) from e

    if not isinstance(data, dict):
        raise ModelError(f"模型输出不是对象：{str(data)[:150]}", retryable=True)

    title = clean_text(data.get("title", ""))
    if not title:
        raise ModelError("模型没有返回 title", retryable=True)

    bullets = []
    for item in data.get("bullets", []):
        text_item = clean_text(item)
        if text_item:
            bullets.append(text_item)

    keywords = []
    for item in data.get("keywords", []):
        text_item = clean_text(item).lower()
        if text_item:
            keywords.append(text_item)

    return {"title": title, "bullets": bullets, "keywords": keywords}


def _backoff_delay(
    attempt: int,
    base: float = 1.0,
    cap: float = 8.0,
    retry_after: float | None = None,
) -> float:
    """第 attempt 次重试前该等多久。

    服务端明确说了 Retry-After 就听它的（但不超过上限）；
    否则按 1s、2s、4s 指数增长，再叠一层随机抖动避免所有请求同一时刻涌上去。
    """
    if retry_after is not None:
        return min(float(retry_after), cap)
    nominal = min(cap, base * (2**attempt))
    return nominal * (0.5 + random.random() * 0.5)


def generate_listing(
    name: str,
    category: str,
    features: list[str],
    retries: int = 2,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    sleep: Callable[[float], None] | None = None,
    log: Callable[[str], None] | None = None,
) -> dict:
    """生成 listing 文案。

    暂时性失败（429 / 5xx / 超时 / 输出不是 JSON）按指数退避重试；
    永久性失败（401 密钥错误、400 参数错误）立刻抛出，不做无意义的等待。
    """
    prompt = _PROMPT_TEMPLATE.format(
        name=name,
        category=category,
        features=", ".join(features),
    )

    sleep = sleep or time.sleep
    log = log or print

    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            return _parse_listing(_call_model(prompt))
        except ModelError as e:
            last_error = e
            if not e.retryable:
                # 密钥错了、参数错了，重试一百次也一样，立刻失败
                raise
            if attempt == retries:
                break
            delay = _backoff_delay(attempt, base_delay, max_delay, e.retry_after)
            log(f"[llm] 第 {attempt + 1} 次失败（{e}），{delay:.2f}s 后重试")
            sleep(delay)

    raise RuntimeError(f"生成失败（已重试 {retries} 次）：{last_error}")
