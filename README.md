一个把文件解析成结构化结果的服务。

## 跑起来

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

```bash
curl http://127.0.0.1:8000/health
# {"ok":true}
```

## 当前进度

- [x] 仓库初始化
- [x] 环境搭建（Python 3.13 / FastAPI / uvicorn）
- [x] `/health` 接口
- [ ] Docker 容器化
- [ ] 上传文件并写入数据库
- [ ] 任务状态查询
