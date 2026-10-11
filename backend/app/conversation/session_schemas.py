from pydantic import BaseModel,ConfigDict,Field

class StartChatSession(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message:str=Field(min_length=1,max_length=1000)
    idempotency_key:str|None=Field(default=None,min_length=8,max_length=100)

class ChatMessage(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message:str=Field(min_length=1,max_length=1000)
    idempotency_key:str|None=Field(default=None,min_length=8,max_length=100)
