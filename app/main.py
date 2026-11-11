from fastapi import FastAPI, HTTPException,Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
import logging
from app.schemas import ChatRequest, ChatResponse, HealthResponse
from app.agent import SimpleAgent

logger = logging.getLogger(__name__)
load_dotenv()


@asynccontextmanager
async def lifespan(app:FastAPI):
    app.state.agent = SimpleAgent()
    print(f"Agent启动成功，当前模式: {app.state.agent.mode}")
    yield
    app.state.agent = None

app = FastAPI(lifespan = lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

async def get_agent():
    agent = getattr(app.state,"agent",None)
    if agent is None:
        raise HTTPException(status_code=503,detail="服务正在启动中，请稍后重试")
    return agent

@app.get("/health", response_model=HealthResponse)
async def health():
    mode = "llm" if os.getenv("AGENT_LLM_API_KEY") else "local"
    return {"status":"ok","mode":mode}

@app.post("/chat",response_model=ChatResponse)
async def chat_endpoint(request:ChatRequest,agent_instance=Depends(get_agent)):

    if not request.message.strip():
        raise HTTPException(status_code=400,detail="Message cannot be empty")

    if request.reset:
        agent_instance.reset()

    try:
        reply = await agent_instance.chat(request.message)
    except Exception as e:
        logger.error(f"Agent内部异常:{e}",exc_info=True)
        raise HTTPException(status_code=502,detail="上游服务暂不可用,请稍后重试") from e

    agent_instance.turns += 1

    return {
        "reply":reply,
        "mode":agent_instance.mode,
        "turns":agent_instance.turns
    }