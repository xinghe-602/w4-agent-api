from pydantic import BaseModel
class ChatRequest(BaseModel):
    message: str
    reset: bool = False

