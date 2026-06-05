from pydantic import BaseModel
from typing import Optional


# USER

class UserCreate(BaseModel):
    username: str
    email: str
    password: str


# POST

class PostCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[str] = None


# NEWS

class NewsCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = None


# COMMENT

class CommentCreate(BaseModel):
    content: str
    post_id: int


# VIDEO

class VideoCreate(BaseModel):
    title: str
    description: Optional[str] = None


# MUSIC

class MusicCreate(BaseModel):
    title: str
    artist: Optional[str] = None
