# agent-foundation

跨境电商 listing 文案生成服务。输入产品名、类目和卖点，输出亚马逊风格的标题、五点描述和搜索关键词。

## 能做什么

- 调用大模型生成 listing 文案，不是模板拼接
- 标题自动截断到亚马逊 200 字符上限，且不切断单词
- 清洗模型输出里的排版字符（长破折号 `–`、弯引号 `""`）为 ASCII
- 支持 `mode=mock` 用模板快速返回，方便对比效果和没配 Key 时联调
- 模型调用失败时返回 502 并带上原因，不会用假数据糊弄调用方
- 批量接口一次最多 20 条，线程池并发（默认 4）；单条失败不影响其余，逐条返回原因

## 跑起来

### 1. 装依赖

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows；macOS/Linux 用 source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配 API Key

```bash
cp .env.example .env
```

打开 `.env`，把 `DEEPSEEK_API_KEY` 换成真实 Key。`.env` 已被 `.gitignore` 排除，不会进仓库。

### 3. 启动

```bash
./.venv/Scripts/python.exe -m uvicorn main:app --port 8010
```

打开 http://127.0.0.1:8010/docs 可以直接在页面上试接口。

> 改完代码要手动重启（`Ctrl+C` → `↑` → `Enter`）。不用 `--reload`：它在 Windows 上偶尔检测到改动却不完成重启，会让服务静默地继续跑旧代码。

## 接口

```bash
curl -X POST "http://127.0.0.1:8010/products/describe" \
  -H "Content-Type: application/json" \
  -d '{"name":"Bamboo Cutting Board","category":"kitchen","features":["eco friendly","easy to clean"]}'
```

```json
{
  "title": "Eco Friendly Bamboo Cutting Board for Kitchen Prep, Easy to Clean",
  "bullets": ["Crafted from eco friendly bamboo...", "..."],
  "keywords": ["bamboo cutting board", "..."],
  "char_count": 70,
  "source": "llm"
}
```

加 `?mode=mock` 走模板拼接，不消耗额度，用于对比。

### 批量

```bash
curl -X POST "http://127.0.0.1:8010/products/batch?workers=4" \
  -H "Content-Type: application/json" \
  -d '{"items":[
    {"name":"Bamboo Cutting Board","category":"kitchen","features":["eco friendly"]},
    {"name":"LED Desk Lamp","category":"home","features":["dimmable","usb charging"]}
  ]}'
```

```json
{
  "results": [
    {"index": 0, "name": "Bamboo Cutting Board", "ok": true, "listing": { "...": "..." }, "error": null},
    {"index": 1, "name": "LED Desk Lamp", "ok": false, "listing": null, "error": "模型接口返回 429：..."}
  ],
  "summary": {"total": 2, "success": 1, "failed": 1, "elapsed_seconds": 6.12},
  "source": "llm"
}
```

参数说明：

| 参数 | 默认 | 说明 |
|---|---|---|
| `mode` | `llm` | `mock` 走模板，不消耗额度 |
| `workers` | `4` | 并发数，1–8。调大更快，但可能触发接口限流 |

实测 4 条真实调用：`workers=1` 耗时 16.8 秒，`workers=4` 耗时 5.3 秒。

单条失败不会让整批报错——接口仍返回 200，失败项在 `results` 里标 `ok=false` 并附原因。**部分成功比整体失败更有用**：调用方能直接拿成功的那些去上架，失败的单独重跑。

### 历史记录

每次生成（单条和批量）都会自动存档，可以按时间倒序翻出来。

```bash
curl "http://127.0.0.1:8010/products/history?limit=3"
```

```json
{
  "total": 4,
  "limit": 3,
  "items": [
    {
      "id": 4,
      "name": "LED Desk Lamp",
      "category": "home",
      "features": ["dimmable"],
      "title": "LED Desk Lamp - Home Essential",
      "bullets": ["1. dimmable"],
      "keywords": ["home", "led desk lamp", "dimmable"],
      "char_count": 30,
      "source": "mock",
      "created_at": "2026-11-12T12:17:51+08:00"
    }
  ]
}
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `limit` | `10` | 返回条数，1–100 |
| `source` | 不限 | 只看 `mock` 或 `llm` |

`total` 是符合条件的总数，不受 `limit` 影响，前端可以据此算还有多少页。

数据存在 `data/listings.db`（已 gitignore）。三个设计取舍：

- **数组字段存 JSON 文本**，不建关联表。这里的需求是回溯存档，不是按数组元素查询。
- **每次操作新开连接**。`sqlite3` 连接默认不能跨线程，而批量接口用了线程池，共享连接会抛 `ProgrammingError: SQLite objects created in a thread can only be used in that same thread`。
- **开启 WAL**。默认 journal 模式下写会锁住整个库，批量写入时读请求全被卡住；WAL 让读写可以并发。

落库失败只打印警告、不影响接口返回——存档是我们自己的次要目标，用户要的文案已经生成好了，不该让他重跑一次。


## 结构

```
main.py              组装 app、注册路由、启动时建表
models.py            请求/响应的数据模型与校验规则
config.py            从环境变量读配置
llm.py               调用大模型、清洗标点、解析 JSON
db.py                SQLite 落库与历史查询
routers/
  system.py          /health /version
  greeting.py        /hello
  products.py        /products/describe、/products/batch、/products/history
```

## 进度

- [x] 环境搭建（FastAPI / uvicorn / venv）
- [x] 路由分层与 pydantic 校验
- [x] 产品文案接口（模板版）
- [x] 接入 DeepSeek 生成真实文案
- [x] 标题截断与标点清洗
- [x] 配置与密钥分离（.env）
- [x] 批量处理（并发 + 单条失败隔离）
- [x] 结果落库与历史查询（SQLite）
- [ ] 失败重试退避与超时细分
- [ ] Docker 容器化
