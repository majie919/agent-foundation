"""重试策略的本地验证：用假服务器按剧本返回错误码，不消耗真实额度。

跑法（在项目根目录）：
    .venv/Scripts/python.exe tests/test_retry.py
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import llm  # noqa: E402

# 假服务器按这个列表依次回包，用完后一直重复最后一项
SCRIPT: list[tuple[int, dict | str]] = []
HITS: list[str] = []

OK_BODY = {
    "choices": [
        {
            "message": {
                "content": json.dumps(
                    {
                        "title": "Bamboo Cutting Board for Kitchen",
                        "bullets": ["BPA-free", "Juice groove"],
                        "keywords": ["bamboo board", "cutting board"],
                    }
                )
            }
        }
    ]
}


class FakeDeepSeek(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def do_POST(self):
        # 必须先把请求体读完，否则服务端回包时连接会被重置（Windows 下尤其明显）
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)

        HITS.append(self.path)
        code, body = SCRIPT[min(len(HITS) - 1, len(SCRIPT) - 1)]
        raw = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()

    def log_message(self, *args):
        pass


def serve():
    srv = HTTPServer(("127.0.0.1", 8099), FakeDeepSeek)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def run_case(title, script, **kwargs):
    global SCRIPT
    SCRIPT = script
    HITS.clear()
    waits: list[float] = []
    logs: list[str] = []

    try:
        result = llm.generate_listing(
            "Bamboo Cutting Board",
            "kitchen",
            ["BPA-free"],
            sleep=waits.append,
            log=logs.append,
            **kwargs,
        )
        outcome = f"成功 -> {result['title'][:34]}"
    except Exception as e:
        outcome = f"{type(e).__name__}: {str(e)[:70]}"

    print(f"\n=== {title} ===")
    print(f"  请求次数 : {len(HITS)}")
    print(f"  实际等待 : {[round(w, 2) for w in waits]}")
    for line in logs:
        print(f"  日志     : {line}")
    print(f"  结果     : {outcome}")


def check_backoff():
    print("\n=== 退避时长（nominal 1s / 2s / 4s，含 ±抖动）===")
    samples = {0: [], 1: [], 2: []}
    for _ in range(500):
        for attempt in samples:
            samples[attempt].append(llm._backoff_delay(attempt, 1.0, 8.0))
    for attempt, vals in samples.items():
        nominal = 2**attempt
        print(
            f"  attempt={attempt} 名义 {nominal}s -> "
            f"实测 {min(vals):.2f}s ~ {max(vals):.2f}s"
        )

    print("\n  Retry-After=5  ->", round(llm._backoff_delay(0, 1.0, 8.0, 5.0), 2), "s")
    print("  Retry-After=60 ->", round(llm._backoff_delay(0, 1.0, 8.0, 60.0), 2), "s（被上限截断）")
    print("  第 4 次重试     ->", round(llm._backoff_delay(3, 1.0, 8.0), 2), "s（不超过 cap=8）")


def main():
    srv = serve()
    config.DEEPSEEK_BASE_URL = "http://127.0.0.1:8099"
    config.DEEPSEEK_API_KEY = config.DEEPSEEK_API_KEY or "sk-local-test"

    run_case("429 两次后成功", [(429, {"error": "rate limited"}), (429, {"error": "rate limited"}), (200, OK_BODY)])
    run_case("401 密钥错误（不该重试）", [(401, {"error": "invalid api key"})])
    run_case("500 一直失败（重试用尽）", [(500, {"error": "internal"})])
    run_case("模型输出不是 JSON（可重试）", [(200, {"choices": [{"message": {"content": "抱歉，我无法完成"}}]}), (200, OK_BODY)])

    check_backoff()
    srv.shutdown()


if __name__ == "__main__":
    main()
