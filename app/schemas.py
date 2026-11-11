from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    reset: bool = False


class ChatResponse(BaseModel):
    reply: str
    mode: str
    turns: int


class HealthResponse(BaseModel):
    status: str
    mode: str
