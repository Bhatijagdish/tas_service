from db import Base
from sqlalchemy import Column, Integer, String, TIMESTAMP, func

class SessionHistory(Base):
    __tablename__ = 'SessionHistory'
    instance_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    history_id = Column(String, nullable=False)
    history_name = Column(String, default='New Chat')
    session_creation_timestamp = Column(String, server_default=func.now())
    history_creation_timestamp = Column(String, server_default=func.now())

