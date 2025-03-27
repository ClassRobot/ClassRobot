from .schema import Chatbot
from .client import rag_client


class AsyncRagFlow:
    async def get_chatbots(
        self, page: int = 1, page_size: int = 30, order_by: str = "create_time", desc: bool = True
    ) -> list[Chatbot]:
        response = await rag_client.get(
            "chats", params={"page": page, "page_size": page_size, "order_by": order_by, "desc": desc}
        )
        data = response.json()
        if data["code"] != 0:
            raise Exception(data["message"])
        else:
            return [Chatbot.parse_obj(chat) for chat in data["data"]]


if __name__ == "__main__":
    from asyncio import run

    rag = AsyncRagFlow()

    async def main():
        chatbots = await rag.get_chatbots()
        session = await chatbots[0].create_session()
        reply = await session.ask("怎么申请半工半读")
        print(reply.reference)
        image = await reply.reference.chunks[0].get_image()
        with open("image.jpg", "wb") as f:
            f.write(image)
        await chatbots[0].delete_session([session.id])

    run(main())
