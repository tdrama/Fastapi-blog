from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.core.database import Base  # Adjust this import to match your project structure

class Feed(Base):
    __tablename__ = "feed"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, nullable=False)
    type = Column(String, nullable=False)  # 'news', 'video', or 'music'
    title = Column(String, nullable=False)
    slug = Column(String, nullable=True)
    content = Column(String, nullable=True)
    media = Column(String, nullable=True)
    video_file = Column(String, nullable=True)
    music_file = Column(String, nullable=True)
    views = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
