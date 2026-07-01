from .schema import Chatbot
from .client import rag_client


class AsyncRagFlow:
    """封装 RagFlow 服务的异步客户端能力。"""

    async def get_chatbots(
        self, page: int = 1, page_size: int = 30, order_by: str = "create_time", desc: bool = True
    ) -> list[Chatbot]:
        """获取chatbots。

        参数:
            page (int): page。
            page_size (int): pagesize。
            order_by (str): orderby。
            desc (bool): 描述信息。

        返回:
            list[Chatbot]: 返回处理结果。
        """
        response = await rag_client.get(
            "chats", params={"page": page, "page_size": page_size, "order_by": order_by, "desc": desc}
        )
        data = response.json()
        if data["code"] != 0:
            raise Exception(data["message"])
        else:
            return [Chatbot.model_validate(chat) for chat in data["data"]]


if __name__ == "__main__":
    from asyncio import run

    rag = AsyncRagFlow()

    async def main():
        """运行主入口。"""
        chatbots = await rag.get_chatbots()
        session = await chatbots[0].create_session()
        reply = await session.ask("怎么申请半工半读")
        print(reply.reference)
        if image := await reply.reference.chunks[0].get_image():
            with open("image.jpg", "wb") as f:
                f.write(image)
        else:
            raise Exception("未获取到图片")
        await chatbots[0].delete_session([session.id])

    run(main())
