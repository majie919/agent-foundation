# agent-foundation

跨境电商 listing 文案生成服务。输入产品名、类目和卖点，输出亚马逊风格的标题、五点描述和搜索关键词。

## 能做什么

- 调用大模型生成 listing 文案，不是模板拼接
- 标题自动截断到亚马逊 200 字符上限，且不切断单词
- 清洗模型输出里的排版字符（长破折号 `–`、弯引号 `""`）为 ASCII
- 支持 `mode=mock` 用模板快速返回，方便对比效果和没配 Key 时联调
- 模型调用失败时返回 502 并带上原因，不会用假数据糊弄调用方

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

## 结构

```
main.py              组装 app、注册路由
models.py            请求/响应的数据模型与校验规则
config.py            从环境变量读配置
llm.py               调用大模型、清洗标点、解析 JSON
routers/
  system.py          /health /version
  greeting.py        /hello
  products.py        /products/describe
```

## 进度

- [x] 环境搭建（FastAPI / uvicorn / venv）
- [x] 路由分层与 pydantic 校验
- [x] 产品文案接口（模板版）
- [x] 接入 DeepSeek 生成真实文案
- [x] 标题截断与标点清洗
- [x] 配置与密钥分离（.env）
- [ ] 失败重试退避与超时细分
- [ ] 批量处理与结果落库
- [ ] Docker 容器化
