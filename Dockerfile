# 用 slim 变体：完整版镜像 900MB+，slim 只有 120MB 左右
FROM python:3.12-slim

# PYTHONUNBUFFERED 让 print 和日志立刻输出，否则 docker logs 里要等缓冲区满才看得到
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    TZ=Asia/Shanghai

WORKDIR /app

# 先只拷依赖清单再安装：只要 requirements.txt 没变，这一层就走缓存，
# 改代码时不用重装依赖，构建从 40 秒降到 1 秒
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再拷代码。放在安装依赖之后，才能保住上面那层缓存
COPY . .

# 非 root 运行：容器逃逸时拿到的权限更小。data 目录要事先建好并交出属主，
# 否则挂载卷之后写入会 Permission denied
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8010

# slim 镜像里没有 curl，用 python 自己探活
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=3).status == 200 else 1)"

# 必须绑 0.0.0.0：容器默认的 127.0.0.1 只指容器自己，宿主机映射的端口永远连不上
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
