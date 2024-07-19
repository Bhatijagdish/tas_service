from typing import List
from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    responseLength: str
    session_id: str


class ChangeHistoryNameRequest(BaseModel):
    session_id: str
    history_id: str
    new_name: str


class ViewHistoryRequest(BaseModel):
    session_id: str


class ViewChatHistoryRequest(BaseModel):
    history_id: str


class Response(BaseModel):
    sessionId: str
    history: list
    userIP: str


class TokenCounter(BaseModel):
    query: str


class TypeAndID(BaseModel):
    query: str


class TypeAndID2(BaseModel):
    query: str


class TypeAndID3(BaseModel):
    query: str


class MetadataQuery(BaseModel):
    data_id: str


class QueryUrls(BaseModel):
    data_id: str
    chunk: str


class FetchDataId(BaseModel):
    data_ids: List[str]
    chunk: str


class ChatHistoryRequest(BaseModel):
    query: str
    history_id: str
    session_id: str
    sender: str
