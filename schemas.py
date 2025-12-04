from pydantic import BaseModel
from typing import List, Optional

class FileMeta(BaseModel):
    type: str  # "audio", "document", "presentation", "photo"
    file_id: str
    name: str

class Topic(BaseModel):
    course: int
    title: str
    files: List[FileMeta]

class Course(BaseModel):
    id: int
    title: str

class FileRequest(BaseModel):
    telegram_id: int
    file_id: str
    webapp_token: str

class StatusResponse(BaseModel):
    status: str
    message: str