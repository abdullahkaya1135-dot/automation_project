from pydantic import BaseModel


class LoginRequest(BaseModel):
    pin: str
