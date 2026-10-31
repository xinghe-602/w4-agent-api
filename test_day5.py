"""W4 Day5 验收自检：工程化（目录结构 / lifespan / CORS / .env / requirements）。

运行方式（PyCharm 直接 Run，或终端）：
    venv\\Scripts\\python.exe test_day5.py

和 test_day4.py 一样：这份脚本只定义"什么叫通过"，不提供实现。
唯一的结构要求是 Day5 的任务本身——从平铺文件重构成 app/ 包。
"""

import contextlib
import io
import logging
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

passed, failed, bonus = [], [], []


def check(name, ok, detail="", bonus_item=False):
    mark = "PASS" if ok else "FAIL"
    if bonus_item:
        mark = "PASS" if ok else "TODO(加分)"
        bonus.append(bool(ok))
    else:
        (passed if ok else failed).append(name)
    tail = f"   <- {detail}" if detail else ""
    print(f"{mark}  {name}{tail}")


# ---------------------------------------------------------------- 第 1 部分：文件结构
print("\n== 1. 目录与工程文件 ==")

for rel in ["app/__init__.py", "app/main.py", "app/agent.py", "app/schemas.py"]:
    check(f"存在 {rel}", (ROOT / rel).is_file())

req = ROOT / "requirements.txt"
req_text = req.read_text(encoding="utf-8").lower() if req.is_file() else ""
check("存在 requirements.txt", req.is_file())
for pkg in ["fastapi", "uvicorn", "python-dotenv"]:
    check(f"requirements.txt 含 {pkg}", pkg in req_text, "缺就补一行，版本可不写")

env_ex = ROOT / ".env.example"
env_ex_text = env_ex.read_text(encoding="utf-8") if env_ex.is_file() else ""
check("存在 .env.example", env_ex.is_file())
check(
    ".env.example 说明了 AGENT_LLM_API_KEY",
    "AGENT_LLM_API_KEY" in env_ex_text,
    "空 key 留占位，别写真 key",
)

gi = ROOT / ".gitignore"
gi_text = gi.read_text(encoding="utf-8") if gi.is_file() else ""
check("存在 .gitignore", gi.is_file())
for line in [".env", "venv", "__pycache__"]:
    check(
        f".gitignore 覆盖 {line}",
        any(line in ln for ln in gi_text.splitlines()),
    )

if failed:
    print(f"\n结构还差 {len(failed)} 项，先补齐再跑接口部分。")
    print("目标结构：app/{__init__,main,agent,schemas}.py + requirements.txt + .env.example + .gitignore")
    sys.exit(1)

# ---------------------------------------------------------------- 第 2 部分：模块边界
print("\n== 2. 包导入与模块边界 ==")

try:
    from app.agent import SimpleAgent
    from app.schemas import ChatRequest
    from app.main import app

    check("from app.agent import SimpleAgent", True)
    check("from app.schemas import ChatRequest", True, "请求体模型已从 main.py 挪到 schemas.py")
    check("from app.main import app", True)
except Exception as e:  # noqa: BLE001
    print(f"FAIL  包导入失败：{type(e).__name__}: {e}")
    print("      常见原因：缺 app/__init__.py；或用了 from agent import ... 这种平铺导入")
    sys.exit(1)

import inspect  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

check("SimpleAgent.chat 仍是 async def", inspect.iscoroutinefunction(SimpleAgent.chat))

# ---------------------------------------------------------------- 第 3 部分：lifespan
print("\n== 3. 启动钩子 lifespan ==")


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
health_body = {}
try:
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        with TestClient(app) as c:  # 进入 with 才会触发 startup
            r = c.get("/health")
            if r.status_code == 200:
                health_body = r.json()
finally:
    root_logger.removeHandler(cap)
    root_logger.setLevel(prev_level)

startup_text = (buf.getvalue() + "\n" + "\n".join(cap.lines)).lower()
has_mode_word = "mode" in startup_text or "模式" in startup_text
has_mode_val = "local" in startup_text or "llm" in startup_text
check(
    "启动时打印了当前模式（含 mode + local/llm）",
    has_mode_word and has_mode_val,
    f"捕获到：{(buf.getvalue() + ' '.join(cap.lines)).strip()[:60]!r}",
)
check(
    "GET /health 返回 mode 字段",
    health_body.get("mode") in {"local", "llm"},
    str(health_body),
    bonus_item=True,
)

# ---------------------------------------------------------------- 第 4 部分：CORS
print("\n== 4. CORS 中间件 ==")

has_cors = any(getattr(m, "cls", None) is CORSMiddleware for m in app.user_middleware)
check("app 注册了 CORSMiddleware", has_cors)

allowed = False
acao = ""
try:
    with TestClient(app) as c:
        r = c.options(
            "/chat",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        acao = r.headers.get("access-control-allow-origin", "")
        allowed = r.status_code in (200, 204) and acao in {"*", "http://localhost:5173"}
except Exception as e:  # noqa: BLE001
    print(f"      preflight 异常：{type(e).__name__}: {e}")

check(
    "预检 OPTIONS 返回 Access-Control-Allow-Origin",
    allowed,
    f"status/acao = {acao or '无'}",
)

# ---------------------------------------------------------------- 第 5 部分：接口回归
print("\n== 5. Day1–Day4 能力回归（不能被重构弄坏）==")

with TestClient(app) as c:
    r = c.get("/health")
    check("GET /health -> 200", r.status_code == 200, str(r.status_code))

    r = c.post("/chat", json={"message": "高等数学"})
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    check("POST /chat -> 200 且含 reply", r.status_code == 200 and "reply" in body, f"{r.status_code} {body}")

    r = c.post("/chat", json={"message": "   "})
    check("空消息 -> 400", r.status_code == 400, str(r.status_code))

    r = c.post("/chat", json={})
    check("缺 message -> 422", r.status_code == 422, str(r.status_code))

# ---------------------------------------------------------------- 第 6 部分：配置驱动
print("\n== 6. 配置真的生效（.env / 环境变量 -> mode）==")

probe = (
    "import sys; sys.path.insert(0, '.');"
    "from fastapi.testclient import TestClient;"
    "from app.main import app;"
    "r = TestClient(app).get('/health');"
    "print('MODE=' + str((r.json() or {}).get('mode')))"
)
env = dict(os.environ)
env["AGENT_LLM_API_KEY"] = "sk-test-dummy-not-a-real-key"
env.pop("PYTHONPATH", None)
proc = subprocess.run(
    [sys.executable, "-c", probe],
    cwd=str(ROOT),
    env=env,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
out = (proc.stdout or "").strip()
mode_line = next((ln for ln in out.splitlines() if ln.startswith("MODE=")), "")
check(
    "设置 AGENT_LLM_API_KEY 后 mode 切到 llm",
    mode_line == "MODE=llm",
    mode_line or f"退出码 {proc.returncode}；{((proc.stderr or '').strip().splitlines() or ['无输出'])[-1][:90]}",
)

# ---------------------------------------------------------------- 汇总
print()
if failed:
    print(f"还有 {len(failed)} 项未通过：")
    for n in failed:
        print(f"  - {n}")
else:
    print("必过项全部通过")
if not all(bonus):
    print(f"加分项还有 {bonus.count(False)} 项可做（/health 带 mode）")
