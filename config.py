import os

from dotenv import load_dotenv

load_dotenv()

# 版本号只在这里写一次，/health、/version、app 元信息都引用它。
# 之前三处各写一份，改了两处忘了第三处，接口就报了个过期的版本。
APP_VERSION = "0.5.0"
BUILD_TIME = "2026-11-12 14:50"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")

# ---- 接入方鉴权与限流 ----
# API_KEYS 是"谁能调用我的接口"，和 DEEPSEEK_API_KEY（我去调别人）是两个方向。
# 多个 Key 用英文逗号分隔，方便给不同的人发不同的 Key，将来能按 Key 追责。
API_KEYS = {k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()}

RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "30"))      # 窗口内最多几次
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # 窗口多长（秒）

if not API_KEYS:
    print("[config] 未配置 API_KEYS：生成类接口处于开发模式（不校验 Key，但仍然限流）")

if not DEEPSEEK_API_KEY:
    print("[config] 警告：未配置 DEEPSEEK_API_KEY，调用真实模型时会失败")
    print("[config] 解决：复制 .env.example 为 .env，填入真实 Key")


def require_api_key() -> str:
    """真正要用 Key 的时候才检查，缺了就抛出明确的错误。"""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError(
            "缺少 DEEPSEEK_API_KEY：请复制 .env.example 为 .env 并填入真实 Key"
        )
    return DEEPSEEK_API_KEY
