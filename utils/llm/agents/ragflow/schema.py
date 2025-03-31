from time import time
from typing import Any, List, Optional

from pydantic import Field, BaseModel

from .client import rag_client, file_client


class LLMConfig(BaseModel):
    frequency_penalty: float
    model_name: str
    presence_penalty: float
    temperature: float
    top_p: float


class Variable(BaseModel):
    key: str
    optional: bool


class PromptConfig(BaseModel):
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
    pages: List[List[int]]


class Dataset(BaseModel):
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
    content: str
    role: str


class DocAgg(BaseModel):
    count: int
    doc_id: str
    doc_name: str

    async def get_document(self) -> bytes:
        response = await file_client.get(f"/document/{self.doc_id}")
        try:
            data = response.json()
        except Exception:
            return response.content
        raise Exception(data["message"])


class Chunk(BaseModel):
    content: str
    dataset_id: str
    document_id: str
    document_name: str
    id: str
    image_id: str
    positions: List[List[int]]
    url: Optional[str] = None

    async def get_image(self) -> bytes:
        response = await file_client.get(f"/document/image/{self.image_id}")
        try:
            data = response.json()
        except Exception:
            return response.content
        raise Exception(data["message"])


class MessageReference(BaseModel):
    chunks: List[Chunk]
    doc_aggs: List[DocAgg]
    total: int


class ChatBotMessage(BaseModel):
    answer: str
    audio_binary: Optional[bytes] = None
    created_at: float = Field(description="Unix timestamp of creation time", default_factory=time)
    id: str
    prompt: str
    reference: MessageReference
    session_id: str


class ChatSession(BaseModel):
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
        response = await rag_client.post(
            f"/chats/{self.chat_id}/completions", json={"question": question, "stream": stream, "session_id": self.id}
        )
        data = response.json()
        if data["code"] != 0:
            raise Exception(data["message"])
        else:
            return ChatBotMessage.parse_obj(data["data"])


class Chatbot(BaseModel):
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
        response = await rag_client.post(f"chats/{self.id}/sessions", json={"name": name})
        data = response.json()

        if data["code"] != 0:
            raise Exception(data["message"])
        else:
            return ChatSession.parse_obj(data["data"])

    async def delete_session(self, ids: List[str]):
        response = await rag_client.request("delete", f"/chats/{self.id}/sessions", json={"ids": ids})
        data = response.json()
        if data["code"] != 0:
            raise Exception(data["message"])
