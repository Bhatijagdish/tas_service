from db import Base
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, CheckConstraint, func


class Messages(Base):
    __tablename__ = 'Messages'
    message_id = Column(Integer, primary_key=True, autoincrement=True)
    history_id = Column(String, nullable=False)
    sender = Column(String, CheckConstraint("sender IN ('AI', 'User')"), nullable=False)
    message_text = Column(Text, nullable=False)
    timestamp = Column(String, server_default=func.now())
