# w4-agent-api
这是我w4自己写的agnet，用FastAPI包成HTTP服务

## 接口表
| 方法   | 路径 | 说明          | 请求体                                                     | 说明体 |
|:-----|:--- |:------------|:--------------------------------------------------------|:--- |
| GET  | / | 根路径，返回欢迎信息  | 无                                                       | {"Message": "Hello World!"} |
| GET  | /health | 健康检查，返回服务状态及Agent模式 | 无                                                       | {"status":"ok","mode":"当前agent.mode的值"} |
| GET | /search/{q} | 搜索接口(带路径参数) | 路径参数：q(str):搜素关键词                                       | {"query":"搜索词"} |
| GET | /items | 获取列表数据(带查询参数分页) | 查询参数:skip(int,默认0):跳过数量 limit(int，默认10):返回数量            | {"skip":0,"limit":10} |
| POST | /chat | 发送聊天信息 | 请求体(JSON):{"message":"你的消息","reset":False}(注：字段名根据代码推断) | {"reply":"Agent的回复"} |

## 快速开始
请确保您的电脑已安装 Python 3.9+及以上的版本。在终端中依次执行以下三条命令：

1.创建并激活虚拟环境:
```bash
python -m venv venv
source venv/bin/activate # Windows用户请使用 venv\Scripts\activate
```
2.安装依赖包:
```bash
pip install -r requirements.txt
```
3.启动服务:
```bash
uvicorn app.main:app --reload
```

启动成功后，请打开浏览器http://127.0.0.1:8000/docs查看交互式API文件

## 目录结构
本项目结构清晰，职责分离，主要包含以下三个核心文件:
```text
├── app/
│   ├── main.py       # 装配：负责 FastAPI 实例化、路由挂载、全局异常处理
│   ├── agent.py      # 领域逻辑：核心 Agent 的运行模式及具体业务逻辑处理
│   └── schemas.py    # 契约：定义请求体和响应体的 Pydantic 数据模型（如 ChatRequest）
├── requirements.txt
└── README.md
```

## 配置说明与已知边界 

### 1. 配置说明
本项目支持通过环境变量进行配置，**所有配置均有默认值，不填也能直接运行**。具体变量如下：
*   `AGENT_MODE`：设置 Agent 的运行模式（例如：`dev` 或 `prod`），默认值为 `dev`。可通过 `/health` 接口查看当前模式。
*   `TIMEOUT`：外部请求的超时时间（秒），默认 30。
*   `API_KEY`：调用外部模型服务的密钥（当前未接入大模型，暂不需要填写）。

*(注：项目根目录提供了 `.env.example` 文件，你可以复制并重命名为 `.env` 来修改这些配置)*

### 2. 已知边界 
为了保证项目的透明度，特此说明当前版本的局限性及后续规划：
*   **LLM 分支暂未实现**：目前 `/chat` 接口仅返回模拟的结构化数据，尚未接入真实的大语言模型（计划于 W5 阶段完成接入）。
*   **`kb-agent` 为初版结构**：目前的知识库 Agent 仅实现了基础骨架，代码结构将在 W6 阶段进行重写和优化。
*   **鉴权机制缺失**：当前接口未做身份验证（Auth），仅供本地开发与内部测试使用。