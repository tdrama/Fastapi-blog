from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    BigInteger,
    Float,
    ForeignKey
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    video_file = Column(String(1000), nullable=False)

    file_size = Column(BigInteger, default=0)
    file_size_display = Column(String(100), nullable=True)

    duration = Column(Float, default=0)

    file_hash = Column(String(255), unique=True, nullable=True)

    views = Column(Integer, default=0)
    downloads = Column(Integer, default=0)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # =========================
    # RELATIONSHIPS
    # =========================

    user = relationship("User", back_populates="videos")

    category = relationship("Category", back_populates="videos")

    comments = relationship(
        "Comment",
        back_populates="video",
        cascade="all, delete"
    )
