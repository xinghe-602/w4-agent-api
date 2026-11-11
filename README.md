# W4 Day7 FastAPI Agent
这是一个基于FastAPI构建的纯Python Agent服务

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查，返回 `{"status":"ok","mode":"local"}` |
| POST | `/chat` | 对话接口 |

`POST /chat` 请求体：

```json
{ "message": "高等数学", "reset": false }
```

响应：

```json
{ "reply": "...", "mode": "local", "turns": 1 }
```

- `turns`：包含本次在内的累计轮数，`reset=true` 时清零后重新计数
- 空白 `message` 返回 `400`；字段缺失或类型错误返回 `422`；agent 内部异常返回 `502`

## 快速开始
请确保您的电脑上已经安装了Python 3.12+及以上版本的。在终端中依次执行一下三条命令：
1.创建并激活虚拟环境：
```bash
python -m venv .venv
.\.venv\Scripts\Activate
```

2.安装依赖包
```bash
pip install -r requirements.txt
```

3.启动服务
```bash
uvicorn app.main:app --reload
```
启动成功后，请打开浏览器`http://127.0.0.1:8000/docs` 查看交互式文档

## 目录结构

```
w4-day7-fromscratch/
├── app/
│   ├── main.py        # 路由、lifespan、CORS、错误处理
│   ├── agent.py       # 自写 agent，纯 Python，不依赖 Web 框架
│   └── schemas.py     # Pydantic 请求/响应模型
├── requirements.txt
├── .env.example
└── .gitignore
```

## 环境变量和LLM KEY 接入说明
- **local**:默认状态，使用内置的本地知识库进行关键词匹配。
- **llm**:如需接入真实LLM，请在项目根目录创建`.env`文件，并填入你的API key：
    `AGENT_LLM_API_KEY=your_api_key_here`
注意：`.env`文件包含敏感信息，已加入`.gitignore`,确保它绝不进入版本库。
注意：本仓库的agent是独立编写的本地确定性逻辑；kb-agent不在本仓库，计划在W6重写后把真实逻辑替换进来。