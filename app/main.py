from fastapi import FastAPI, HTTPException
from app.agent import SimpleAgent
from app.schemas import ChatRequest
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()


agent = SimpleAgent()
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[startup] agent mode = {agent.mode}")
    yield
app = FastAPI(lifespan = lifespan)



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"Message": "Hello World!"}

@app.get("/health")
async def read_health():
    return {"status":"ok","mode":agent.mode}

@app.get("/search/{q}")
async def read_search(q:str):
    return {"query":q}

@app.get("/items")
async def read_items(skip: int = 0, limit: int = 10):
    return {"skip":skip,"limit":limit}

@app.post("/chat")
async def create_message(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400,detail="消息内容不能为空")
    try:
        if req.reset:
            agent.reset()

        reply = await agent.chat(req.message)
        return {"reply":reply}
    except Exception as e:
        raise HTTPException(status_code=502,detail=f"调用Agent失败:{str(e)}") from e
