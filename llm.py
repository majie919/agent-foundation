"""调用 DeepSeek 生成 listing 文案。

对外只有两个函数：
- clean_text()        清洗模型输出里的排版字符
- generate_listing()  生成标题 / 五点 / 关键词
"""

import json
import re
import urllib.error
import urllib.request

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
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:200]
        raise RuntimeError(f"模型接口返回 {e.code}：{detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"连不上模型接口：{e.reason}") from e

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"模型返回格式异常：{str(data)[:200]}") from e


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


def generate_listing(
    name: str,
    category: str,
    features: list[str],
    retries: int = 1,
) -> dict:
    """生成 listing 文案。失败会重试，最终失败则抛 RuntimeError。"""
    prompt = _PROMPT_TEMPLATE.format(
        name=name,
        category=category,
        features=", ".join(features),
    )

    last_error: Exception | None = None

    for _ in range(retries + 1):
        try:
            raw = _call_model(prompt)
            data = _extract_json(raw)

            title = clean_text(data.get("title", ""))
            if not title:
                raise ValueError("模型没有返回 title")

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

        except Exception as e:  # noqa: BLE001 - 任何失败都值得重试一次
            last_error = e

    raise RuntimeError(f"生成失败（已重试 {retries} 次）：{last_error}")
