from sqlalchemy import Column, Integer, String, Text, BigInteger, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Music(Base):
    __tablename__ = "music"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(255), nullable=False)
    artist = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    music_file = Column(String(500), nullable=False)
    cover_image = Column(String(500), nullable=True)

    file_size = Column(BigInteger, default=0)
    file_size_display = Column(String(50), nullable=True)

    duration = Column(Integer, default=0)

    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)

    file_hash = Column(String(64), unique=True, index=True, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    downloads = Column(Integer, default=0)

    # =========================
    # RELATIONSHIPS
    # =========================

    user = relationship("User", back_populates="musics")

    category = relationship("Category", back_populates="musics")

    comments = relationship(
        "Comment",
        back_populates="music",
        cascade="all, delete"
    )
