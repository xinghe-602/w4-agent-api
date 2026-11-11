"""W4 Day7 验收：从零重搭一个 agent 服务（整合日）。

运行方式（在 w4-day7-fromscratch 目录下，用装了 fastapi 的解释器）：
    & "D:\\Self-improvement\\w4-fastapi\\pythonProject\\venv\\Scripts\\python.exe" test_day7.py

这份脚本只定义"什么叫通过"，不提供实现。
它会做四件事：
  1) 检查工程结构是否完整（有没有 README / .gitignore / requirements）
  2) 检查模块边界（agent.py 必须能脱离 Web 框架独立存在）
  3) 用 TestClient 打接口，验证状态码语义与会话状态
  4) 真起一个 uvicorn 进程做端到端验证（不是只有 TestClient 能跑）

和 Day4/Day5 的脚本相比，Day7 的契约多了两个字段：
  POST /chat 必须返回 mode 与 turns。
原项目 README 里承诺了这两个字段但没实现——Day7 就是把它补上，
顺便证明这次是重写的，不是把旧代码复制过来。
"""

import asyncio
import contextlib
import io
import inspect
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

passed, failed = [], []


def check(name, ok, detail=""):
    (passed if ok else failed).append(name)
    mark = "PASS" if ok else "FAIL"
    tail = f"   <- {detail}" if detail else ""
    print(f"{mark}  {name}{tail}")


# ---------------------------------------------------------------- 0. 依赖
print("\n== 0. 运行环境 ==")

missing = []
for mod in ["fastapi", "uvicorn", "dotenv", "httpx"]:
    try:
        __import__(mod)
    except ImportError:
        missing.append(mod)
if missing:
    print(f"FAIL  缺少依赖：{', '.join(missing)}")
    print("      先装依赖再跑：pip install -r requirements.txt")
    sys.exit(1)
check("fastapi / uvicorn / dotenv / httpx 均可导入", True)

try:
    import fastapi  # noqa: F401

    ver = getattr(fastapi, "__version__", "?")
except Exception:  # noqa: BLE001
    ver = "?"
print(f"      fastapi 版本 {ver}")


# ---------------------------------------------------------------- 1. 工程结构
print("\n== 1. 目录与工程文件 ==")

FILES = [
    "app/__init__.py",
    "app/main.py",
    "app/agent.py",
    "app/schemas.py",
    "requirements.txt",
    "README.md",
    ".gitignore",
    ".env.example",
]
for rel in FILES:
    check(f"存在 {rel}", (ROOT / rel).is_file())

req_text = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower() if (ROOT / "requirements.txt").is_file() else ""
for pkg in ["fastapi", "uvicorn", "python-dotenv"]:
    check(f"requirements.txt 含 {pkg}", pkg in req_text, "缺就补一行")

gi_text = (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").is_file() else ""
for line in [".env", "venv", "__pycache__"]:
    check(
        f".gitignore 覆盖 {line}",
        any(line in ln for ln in gi_text.splitlines()),
    )

env_ex_text = (ROOT / ".env.example").read_text(encoding="utf-8") if (ROOT / ".env.example").is_file() else ""
check(
    ".env.example 含 AGENT_LLM_API_KEY 占位",
    "AGENT_LLM_API_KEY" in env_ex_text,
    "只留占位，别写真实 key",
)

if failed:
    print(f"\n结构缺 {len(failed)} 项，先补齐再跑后面的部分。")
    print("目标：app/{__init__,main,agent,schemas}.py + requirements.txt + README.md + .gitignore + .env.example")
    sys.exit(1)


# ---------------------------------------------------------------- 2. 模块边界
print("\n== 2. 模块边界：agent 必须能脱离 Web 框架 ==")

agent_src = (ROOT / "app" / "agent.py").read_text(encoding="utf-8")
banned = ["import fastapi", "from fastapi", "import uvicorn", "from pydantic"]
hits = [b for b in banned if b in agent_src]
check(
    "agent.py 不 import fastapi / uvicorn / pydantic",
    not hits,
    f"发现 {hits}" if hits else "纯 Python，可被任意入口复用",
)

try:
    from app.agent import SimpleAgent

    check("from app.agent import SimpleAgent 可导入", True)
    check(
        "SimpleAgent.chat 是 async def",
        inspect.iscoroutinefunction(SimpleAgent.chat),
    )
except Exception as e:  # noqa: BLE001
    import traceback

    traceback.print_exc()
    check("from app.agent import SimpleAgent 可导入", False, f"{type(e).__name__}: {e}")

try:
    from app.schemas import ChatRequest

    fields = set(getattr(ChatRequest, "model_fields", {}))
    check("ChatRequest 定义在 app/schemas.py", True, f"字段 {sorted(fields)}")
    check("ChatRequest 有 message 必填字段", "message" in fields)
    check("ChatRequest 的 reset 有默认值", "reset" in fields and not ChatRequest.model_fields["reset"].is_required())
except Exception as e:  # noqa: BLE001
    check("ChatRequest 定义在 app/schemas.py", False, f"{type(e).__name__}: {e}")

try:
    from app import agent as agent_mod
    from app.main import app
except Exception as e:  # noqa: BLE001
    print(f"\nFAIL  from app.main import app 失败：{type(e).__name__}: {e}")
    print("      常见原因：缺 app/__init__.py；缺 __init__.py 时包导入会失败")
    sys.exit(1)


# ---------------------------------------------------------------- 3. 接口与状态
print("\n== 3. 接口契约（/health、/chat 的字段与状态）==")

from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import get_agent  # noqa: E402


def body_of(r):
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {}


with TestClient(app) as c:
    r = c.get("/health")
    hb = body_of(r)
    check("GET /health -> 200", r.status_code == 200, str(r.status_code))
    check("/health 返回 status=ok", hb.get("status") == "ok", str(hb))
    health_mode = hb.get("mode")
    check("/health 返回 mode ∈ {local, llm}", health_mode in {"local", "llm"}, str(hb))

    # 第一轮用 reset 把状态归零，避免受之前运行残留影响
    r = c.post("/chat", json={"message": "高等数学", "reset": True})
    b1 = body_of(r)
    check("POST /chat -> 200", r.status_code == 200, str(r.status_code))
    check("/chat 返回 reply 且非空", isinstance(b1.get("reply"), str) and b1.get("reply").strip() != "", str(b1)[:80])
    check("/chat 返回 mode", b1.get("mode") in {"local", "llm"}, str(b1.get("mode")))
    check("/chat 与 /health 的 mode 一致", b1.get("mode") == health_mode, f"{b1.get('mode')} vs {health_mode}")
    t1 = b1.get("turns")
    check("reset=true 后 turns 从 1 开始", t1 == 1, f"turns={t1}")

    r2 = body_of(c.post("/chat", json={"message": "机器学习"}))
    r3 = body_of(c.post("/chat", json={"message": "线性代数"}))
    seq = (t1, r2.get("turns"), r3.get("turns"))
    check("连续对话 turns 递增 1,2,3", seq == (1, 2, 3), f"实际 {seq}")

    # reset 必须真的清空历史，不是摆设
    r4 = body_of(c.post("/chat", json={"message": "高等代数", "reset": True}))
    check("再次 reset=true，turns 归 1", r4.get("turns") == 1, f"turns={r4.get('turns')}")

    # 知识库命中检测放在下面单独做（需要新建实例读 knowledge_base，不能塞在 with 里）


# 知识库逐条命中：这一项专门抓「return 写在 for 循环体内」这类缩进 bug
# —— 那样写只有第一条能命中，其余全部落到兜底语，肉眼很难发现
inst = SimpleAgent()
kb = getattr(inst, "knowledge_base", None)
if not isinstance(kb, dict) or len(kb) < 5:
    got_n = len(kb) if isinstance(kb, dict) else 0
    check(
        "SimpleAgent 暴露 knowledge_base（dict，≥5 条）",
        False,
        f"实际类型 {type(kb).__name__}，条数 {got_n}",
    )
else:
    check("SimpleAgent 暴露 knowledge_base（dict，≥5 条）", True, f"{len(kb)} 条")
    missed = []
    for k in kb:
        got = asyncio.run(inst.chat(k))
        if not (isinstance(got, str) and kb[k] in got):
            missed.append((k, str(got)[:24]))
    check(
        "知识库每一条都能命中（循环里 return 缩进错会在这里暴露）",
        not missed,
        f"未命中 {len(missed)}/{len(kb)} 条，例：{missed[:2]}" if missed else f"{len(kb)}/{len(kb)} 命中",
    )
    unknown = asyncio.run(inst.chat("量子色动力学里的胶子禁闭是什么"))
    check(
        "未知问法落到兜底语，不抛异常",
        isinstance(unknown, str) and unknown.strip() != "" and unknown not in kb.values(),
        f"reply={str(unknown)[:30]!r}",
    )


# ---------------------------------------------------------------- 4. 状态码语义
print("\n== 4. 状态码语义（400 / 422 / 502 的归属）==")

with TestClient(app) as c:
    r = c.post("/chat", json={"message": "   "})
    check("空白消息 -> 400（业务校验，你自己写的）", r.status_code == 400, f"{r.status_code} {r.text[:60]}")

    r = c.post("/chat", json={})
    check("缺 message -> 422（框架校验，Pydantic 自动）", r.status_code == 422, str(r.status_code))

    r = c.post("/chat", json={"message": 123})
    check("message 类型错 -> 422", r.status_code == 422, f"{r.status_code}（Pydantic v2 不再强转 int->str）")

    r = c.post("/chat", json={"message": "你好", "reset": "maybe"})
    check("reset 类型错 -> 422", r.status_code == 422, str(r.status_code))


# 上游故障注入：把 chat 换成会抛错的实现，验证 502 而不是 500
origin_chat = agent_mod.SimpleAgent.chat


async def boom(self, message):
    raise RuntimeError("模拟上游模型服务挂了")


agent_mod.SimpleAgent.chat = boom
status_ok = False
status_note = ""
try:
    with TestClient(app) as c:
        try:
            r = c.post("/chat", json={"message": "你好"})
            status_ok = r.status_code == 502
            status_note = f"{r.status_code} {r.text[:60]}"
        except Exception as e:  # noqa: BLE001
            status_note = f"异常直接抛给客户端（没转成 502）：{type(e).__name__}: {str(e)[:50]}"
    check("agent 抛异常 -> 502（不是 500，也不是直接崩）", status_ok, status_note)
finally:
    agent_mod.SimpleAgent.chat = origin_chat


# 就绪检查：agent 未初始化时必须 503，而不是 500 或 AttributeError
# 依赖函数可能是 def 也可能是 async def，两种都要能测
async def _resolve_agent():
    maybe = get_agent()
    if inspect.isawaitable(maybe):
        return await maybe
    return maybe


_sentinel = object()
_saved_agent = getattr(app.state, "agent", _sentinel)
app.state.agent = None
try:
    try:
        asyncio.run(_resolve_agent())
        ready_ok, ready_note = False, "没有抛异常，直接返回了 agent"
    except HTTPException as e:
        ready_ok, ready_note = e.status_code == 503, f"{e.status_code} {e.detail}"
    except Exception as e:  # noqa: BLE001
        ready_ok, ready_note = False, f"{type(e).__name__}: {e}"
finally:
    if _saved_agent is _sentinel:
        delattr(app.state, "agent")
    else:
        app.state.agent = _saved_agent
check("agent 未就绪 -> 503（不是 500 / AttributeError）", ready_ok, ready_note)


# ---------------------------------------------------------------- 5. 启动钩子与 CORS
print("\n== 5. lifespan 与 CORS ==")


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


cap = Capture()
root_logger = logging.getLogger()
root_logger.addHandler(cap)
prev_level = root_logger.level
root_logger.setLevel(logging.INFO)

buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        with TestClient(app) as c:
            c.get("/health")
finally:
    root_logger.removeHandler(cap)
    root_logger.setLevel(prev_level)

startup_text = (buf.getvalue() + "\n" + "\n".join(cap.lines)).lower()
check(
    "启动时打印当前 mode",
    ("mode" in startup_text or "模式" in startup_text) and ("local" in startup_text or "llm" in startup_text),
    f"捕获 {startup_text.strip()[:60]!r}",
)

try:
    from fastapi.middleware.cors import CORSMiddleware

    has_cors = any(getattr(m, "cls", None) is CORSMiddleware for m in app.user_middleware)
    check("注册了 CORSMiddleware", has_cors)
except Exception as e:  # noqa: BLE001
    check("注册了 CORSMiddleware", False, str(e))


# ---------------------------------------------------------------- 6. 端到端：真起 uvicorn
print("\n== 6. 端到端：真起一个 uvicorn 进程 ==")


def port_free(p):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.connect_ex(("127.0.0.1", p)) != 0


PORT = 8123
if not port_free(PORT):
    print(f"SKIP  端口 {PORT} 被占用，跳过端到端测试")
else:
    import urllib.error
    import urllib.request

    env = dict(os.environ)
    env.pop("AGENT_LLM_API_KEY", None)  # 端到端跑本地模式
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    ok_health = ok_docs = False
    last_err = ""
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            if proc.poll() is not None:
                last_err = "uvicorn 进程已退出"
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1) as resp:
                    ok_health = resp.status == 200
                    if ok_health:
                        break
            except Exception as e:  # noqa: BLE001
                last_err = f"{type(e).__name__}"
                time.sleep(0.4)

        if ok_health:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/docs", timeout=3) as resp:
                    html = resp.read().decode("utf-8", "replace").lower()
                    ok_docs = resp.status == 200 and ("swagger" in html or "openapi" in html)
            except Exception as e:  # noqa: BLE001
                last_err = f"/docs {type(e).__name__}"
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    check("uvicorn 能真起服务并响应 /health", ok_health, "" if ok_health else (last_err or f"port {PORT}"))
    check("/docs 可访问（Swagger 页面）", ok_docs, "" if ok_docs else (last_err or "页面不含 swagger/openapi 关键字"))


# ---------------------------------------------------------------- 7. README
print("\n== 7. README 是否让访客 30 秒看懂 ==")

readme = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").is_file() else ""
low = readme.lower()
check("README 写了启动命令 uvicorn", "uvicorn" in low)
check("README 提到 /docs", "/docs" in low)
check("README 说明如何接 LLM key", "agent_llm_api_key" in low or "api key" in low or "apikey" in low)
check(
    "README 有诚实说明（自己写的 agent / W6 重写 kb-agent）",
    any(k in readme for k in ["自己写", "独立编写", "本人", "W6"]),
    "写明：本地 agent 为本次自写，kb-agent 于 W6 重写，不冒用",
)
check("README 提到 .env 不进版本库", ".env" in readme and (".gitignore" in low or "忽略" in readme))


# ---------------------------------------------------------------- 汇总
print()
if failed:
    print(f"还有 {len(failed)} 项未通过：")
    for n in failed:
        print(f"  - {n}")
    print("\n按顺序修：结构 -> 导入 -> 契约 -> 状态码 -> 端到端 -> 文档")
    sys.exit(1)
else:
    print("全部通过：Day7 达标——不查资料从零搭出了有接口 / 有校验 / 能异步 / 有文档的 agent 服务")
