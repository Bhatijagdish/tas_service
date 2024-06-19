from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    history: list
    responseLength: str
    history_id: str
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
