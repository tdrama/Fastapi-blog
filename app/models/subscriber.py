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
# SUBSCRIBER MODEL
# =========================

class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String(255), unique=True, nullable=False)

    subscribed_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
