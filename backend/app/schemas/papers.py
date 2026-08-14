from pydantic import BaseModel
from typing import Optional


class PaperResponse(BaseModel):
    id: str
    title: str
    filename: str
    status: str
    text_length: int
    message: str