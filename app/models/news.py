from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class News(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True)

    content = Column(Text, nullable=False)

    image = Column(String(500), nullable=True)
    image_hash = Column(String(255), unique=True, nullable=True)
    image_size = Column(Integer, nullable=True)

    tags = Column(String(255), nullable=True)

    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)

    is_published = Column(Boolean, default=True)

    author_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # RELATIONSHIPS
    author = relationship("User", back_populates="news")

    category = relationship("Category", back_populates="news")

    comments = relationship(
        "Comment",
        back_populates="news",
        cascade="all, delete"
    )
