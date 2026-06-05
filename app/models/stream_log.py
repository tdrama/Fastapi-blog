from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime
)

from sqlalchemy.sql import func
from app.core.database import Base


class StreamLog(Base):
    __tablename__ = "stream_logs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    content_type = Column(
        String(50),
        nullable=False
    )

    content_id = Column(
        Integer,
        nullable=False
    )

    ip_address = Column(
        String(100),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
