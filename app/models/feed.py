from pydantic import BaseModel
from datetime import datetime

class FeedItem(BaseModel):
    id: int
    type: str
    title: str
    created_at: datetime
    image: str | None
    slug: str | None
    views: int
    # DO NOT include user.email, user.hashed_password, etc

    class Config:
        from_attributes = True  # lets you build from SQLAlchemy objects
