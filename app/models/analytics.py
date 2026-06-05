from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

# =========================
# ANALYTICS MODEL
# =========================

class Analytics(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, index=True)

    page = Column(String(255), nullable=True)

    ip_address = Column(String(255), nullable=True)

    user_agent = Column(Text, nullable=True)

    visits = Column(Integer, default=1)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
