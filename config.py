import os

from dotenv import load_dotenv

load_dotenv()

# 版本号只在这里写一次，/health、/version、app 元信息都引用它。
# 之前三处各写一份，改了两处忘了第三处，接口就报了个过期的版本。
APP_VERSION = "0.4.0"
BUILD_TIME = "2026-11-12 12:30"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")

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
