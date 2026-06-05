from sqlalchemy import (
    Column,
    Integer,
    Text,
    ForeignKey,
    DateTime,
    String
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Comment(Base):

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)

    content = Column(
        Text,
        nullable=False
    )

    name = Column(
        String(100),
        nullable=True
    )

    video_id = Column(
        Integer,
        ForeignKey("videos.id"),
        nullable=True
    )

    music_id = Column(
        Integer,
        ForeignKey("music.id"),
        nullable=True
    )

    news_id = Column(
        Integer,
        ForeignKey("news.id"),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # ====================================
    # RELATIONSHIPS
    # ====================================

    video = relationship(
        "Video",
        back_populates="comments"
    )

    music = relationship(
        "Music",
        back_populates="comments"
    )

    news = relationship(
        "News",
        back_populates="comments"
    )
