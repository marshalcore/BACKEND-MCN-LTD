from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str | None = None

class TokenData(BaseModel):
    unique_id: str | None = None
    type: str | None = None  # 'access' or 'refresh'

class TokenCreate(BaseModel):
    unique_id: str
    password: str