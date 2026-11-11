import asyncio
import os


class SimpleAgent:
    """本地确定性 agent：关键词匹配，不依赖任何外部 key。"""

    def __init__(self) -> None:
        self.turns = 0
        self.mode = "llm" if os.getenv("AGENT_LLM_API_KEY") else "local"
        self.knowledge_base = {
            "高等数学": "高等数学是研究数量、结构、变化以及空间模型等概念的一门学科。",
            "线性代数": "线性代数是数学的一个分支，主要处理向量空间和线性映射",
            "概率论": "概率论是研究随机现象数量规律的数学分支。",
            "计算机": "计算机是现代一种用于高速计算的电子计算机器。",
            "Python": "Python是一种广泛使用的高级编程语言。",
            "人工智能": "人工智能是研究、开发用于模拟、延伸和拓展人的智能的理论、方法、技术及应用系统的一门新的技术科学。",
        }
        self.fallback = "抱歉，我的本地知识库中暂时没有关于这个问题的解释。"

    def _match(self, message: str) -> str | None:
        msg = message.lower()
        for key, answer in self.knowledge_base.items():
            if key.lower() in msg:
                return answer
        return None

    async def _chat_llm(self, message: str) -> str:
        # 预留接入点：W6 用 httpx.AsyncClient 调 OpenAI 兼容接口，届时从这里接
        raise NotImplementedError("LLM 分支尚未接入；移除 AGENT_LLM_API_KEY 可回到本地模式")

    async def chat(self, message: str) -> str:
        if self.mode == "llm":
            return await self._chat_llm(message)
        await asyncio.sleep(0.05)
        return self._match(message) or self.fallback

    def reset(self) -> None:
        self.turns = 0


if __name__ == "__main__":
    async def main() -> None:
        agent = SimpleAgent()
        print(await agent.chat("高等数学"))
        print(await agent.chat("什么是机器学习"))
        print(f"mode = {agent.mode}")

    asyncio.run(main())
