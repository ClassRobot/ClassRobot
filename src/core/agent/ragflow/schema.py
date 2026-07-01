from time import time
from typing import Any, List, Optional

from nonebot import logger
from pydantic import Field, BaseModel

from .client import rag_client, file_client


class LLMConfig(BaseModel):
    """描述llmconfig的配置项。"""

    frequency_penalty: float
    model_name: str
    presence_penalty: float
    temperature: float
    top_p: float


class Variable(BaseModel):
    """描述variable使用的配置或数据结构。"""

    key: str
    optional: bool


class PromptConfig(BaseModel):
    """描述提示词配置的配置项。"""

    empty_response: str
    keyword: bool
    keywords_similarity_weight: float
    opener: str
    prompt: str
    reasoning: bool
    refine_multiturn: bool
    rerank_model: str
    show_quote: bool
    similarity_threshold: float
    tavily_api_key: str
    top_n: int
    tts: bool
    use_kg: bool
    variables: List[Variable]


class ParserConfig(BaseModel):
    """描述parser配置的配置项。"""

    pages: List[List[int]]


class Dataset(BaseModel):
    """描述dataset使用的配置或数据结构。"""

    avatar: Optional[Any] = None
    chunk_num: int
    create_date: str
    create_time: int
    created_by: str
    description: Optional[str] = None
    doc_num: int
    embd_id: str
    id: str
    language: str
    name: str
    pagerank: float
    parser_config: ParserConfig
    parser_id: str
    permission: str
    similarity_threshold: float
    status: str
    tenant_id: str
    token_num: int
    update_date: str
    update_time: int
    vector_similarity_weight: float


class ChatMessage(BaseModel):
    """描述聊天消息使用的配置或数据结构。"""

    content: str
    role: str


class DocAgg(BaseModel):
    """描述Wordagg使用的配置或数据结构。"""

    count: int
    doc_id: str
    doc_name: str

    async def get_document(self) -> bytes:
        """获取document。"""
        response = await file_client.get(f"/document/{self.doc_id}")
        try:
            data = response.json()
        except Exception:
            return response.content
        raise Exception(data["message"])


class Chunk(BaseModel):
    """描述chunk使用的配置或数据结构。"""

    content: str
    dataset_id: str
    document_id: str
    document_name: str
    id: str
    image_id: str
    positions: List[List[int]]
    url: Optional[str] = None

    async def get_image(self) -> bytes | None:
        """获取图片。"""
        if not self.image_id:
            logger.error(f"ragflow chunk error url: {self.url}; image_id: {self.image_id};")
            return None
        response = await file_client.get(f"/document/image/{self.image_id}")
        try:
            data = response.json()
        except Exception:
            return response.content
        raise Exception(data["message"])


class MessageReference(BaseModel):
    """描述消息reference使用的配置或数据结构。"""

    chunks: List[Chunk]
    doc_aggs: List[DocAgg]
    total: int


class ChatBotMessage(BaseModel):
    """描述聊天bot消息使用的配置或数据结构。"""

    answer: str
    audio_binary: Optional[bytes] = None
    created_at: float = Field(description="Unix timestamp of creation time", default_factory=time)
    id: str
    prompt: str
    reference: MessageReference
    session_id: str


class ChatSession(BaseModel):
    """描述聊天会话使用的配置或数据结构。"""

    chat_id: str
    create_date: str
    create_time: int
    id: str
    messages: List[ChatMessage]
    name: str
    update_date: str
    update_time: int
    user_id: str

    async def ask(self, question: str, stream: bool = False):
        """处理ask相关逻辑。

        参数:
            question (str): question。
            stream (bool): stream。
        """
        response = await rag_client.post(
            f"/chats/{self.chat_id}/completions", json={"question": question, "stream": stream, "session_id": self.id}
        )
        data = response.json()
        if data["code"] != 0:
            raise Exception(data["message"])
        else:
            return ChatBotMessage.model_validate(data["data"])


class Chatbot(BaseModel):
    """描述chatbot使用的配置或数据结构。"""

    avatar: str
    create_date: str
    create_time: int
    datasets: List[Dataset]
    description: str
    do_refer: str
    id: str
    language: str
    llm: LLMConfig
    name: str
    prompt: PromptConfig
    prompt_type: str
    status: str
    tenant_id: str
    top_k: int
    update_date: str
    update_time: int

    async def create_session(self, name: str = "New Session"):
        """创建会话。

        参数:
            name (str): 名称。
        """
        response = await rag_client.post(f"chats/{self.id}/sessions", json={"name": name})
        data = response.json()

        if data["code"] != 0:
            raise Exception(data["message"])
        else:
            return ChatSession.model_validate(data["data"])

    async def delete_session(self, ids: List[str]):
        """删除会话。

        参数:
            ids (List[str]): 标识列表。
        """
        response = await rag_client.request("delete", f"/chats/{self.id}/sessions", json={"ids": ids})
        data = response.json()
        if data["code"] != 0:
            raise Exception(data["message"])
