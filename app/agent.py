import asyncio
import os
class SimpleAgent:
    def __init__(self) -> None:
        if os.getenv("AGENT_LLM_API_KEY"):
            self.mode = "llm"
        else:
            self.mode = "local"
        self.kb = {
            "高等数学":"大学理工科必学科目",
            "线性代数":"数学专业的线性基础科目",
            "高等代数":"关于代数的基础内容",
            "大数据下的python基础":"利用python来对大数据进行处理",
            "机器学习":"AI大模型的理论基础之一"
        }
        self.fallback = "我暂时只知道这些内容，你换个说法试试"

    def _match(self,message) -> str:
        msg = message.lower()
        for key,answer in self.kb.items():
            if key.lower() in msg:
                return answer
        return None
    async def _chat_llm(self,message):
        raise NotImplementedError("大模型分支暂未实现，请移除AGENT_LLM_API_KEY以使用本地模式")
    async def chat(self,message:str) ->str:
        if self.mode == "llm":
            return  await self._chat_llm(message)
        await asyncio.sleep(0.05)
        answer = self._match(message)
        # TODO: 本地未命中时接 LLM（Day 5/6 填真实调用）
        if answer is not None:
            return answer
        return self.fallback

    def reset(self):
        pass

if __name__ == "__main__":
    async def main():
        a = SimpleAgent()
        print(await a.chat("什么是高等数学"))
        print(await a.chat("机器学习"))
        print(f"mode = {a.mode}")
    asyncio.run(main())
