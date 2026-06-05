from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)

    # =========================
    # RELATIONSHIPS
    # =========================

    news = relationship(
        "News",
        back_populates="category"
    )

    videos = relationship(
        "Video",
        back_populates="category"
    )

    musics = relationship(
        "Music",
        back_populates="category"
    )
