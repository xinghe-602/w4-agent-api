"""W4 Day4 验收自检：异步 /chat + 状态码归属。

运行方式（PyCharm 直接 Run，或终端）：
    venv\\Scripts\\python.exe test_day4.py

这份脚本只定义"什么叫通过"，不提供实现。改完 main.py / agent.py 后
反复跑它，直到全部 PASS。
"""

import asyncio
import inspect
import time

import httpx
from fastapi.testclient import TestClient

from app import agent as agent_mod  # 你的 app/agent.py
from app.main import app  # 你的 app/main.py

client = TestClient(app)
client.__enter__()  # Day7 起 agent 在 lifespan 中初始化，必须触发启动钩子才有实例
results = []


def check(name, ok, detail=""):
    results.append(ok)
    mark = "PASS" if ok else "FAIL"
    tail = f"   <- {detail}" if detail else ""
    print(f"{mark}  {name}{tail}")


# 1. Day4 核心：agent.chat 必须是 async def
check(
    "agent.chat 是 async def",
    inspect.iscoroutinefunction(agent_mod.SimpleAgent.chat),
)

# 2. 健康检查
r = client.get("/health")
check("GET /health -> 200", r.status_code == 200, str(r.status_code))

# 3. 正常对话：必须返回 reply 字段，说明路由真的调了 agent
r = client.post("/chat", json={"message": "高等数学"})
body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
check(
    "POST /chat -> 200 且返回 reply",
    r.status_code == 200 and "reply" in body,
    f"{r.status_code} {body}",
)

# 4. 业务校验：字段合法但语义为空 -> 400
r = client.post("/chat", json={"message": "   "})
check("空消息 -> 400", r.status_code == 400, f"{r.status_code} {r.text[:80]}")

# 5. 框架校验：缺必填字段 -> 422（FastAPI 自动，不用你写）
r = client.post("/chat", json={})
check("缺 message -> 422", r.status_code == 422, str(r.status_code))

# 6. 上游异常：agent 抛错 -> 502
origin = agent_mod.SimpleAgent.chat


async def boom(self, message):
    raise RuntimeError("模拟上游 LLM 挂了")


agent_mod.SimpleAgent.chat = boom
try:
    r = client.post("/chat", json={"message": "你好"})
    check("agent 异常 -> 502", r.status_code == 502, f"{r.status_code} {r.text[:80]}")
finally:
    agent_mod.SimpleAgent.chat = origin


# 7. 加分项：验证并发真的没被串行放大
#    想让这项有说服力，请在 agent.chat 里加一句 await asyncio.sleep(0.1)
#    模拟 LLM 延迟：串行会是 0.5s+，真正的异步应 < 0.3s
async def concurrent():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        t0 = time.perf_counter()
        await asyncio.gather(
            *[ac.post("/chat", json={"message": "机器学习"}) for _ in range(5)]
        )
        return time.perf_counter() - t0


cost = asyncio.run(concurrent())
check("5 个并发请求耗时 < 1s", cost < 1.0, f"{cost:.3f}s")

failed = results.count(False)
print()
print("全部通过" if failed == 0 else f"还有 {failed} 项未通过")
