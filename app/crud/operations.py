from models import Messages
from db import Session
from sqlalchemy.orm import class_mapper


def model_to_dict(model):
    """Convert a SQLAlchemy model instance into a dictionary."""
    if model is None:
        return None
    columns = [c.key for c in class_mapper(model.__class__).columns]
    return {c: getattr(model, c) for c in columns}


def insert_message(db: Session, session_id, history_id, sender, message_text):
    message = Messages(session_id=session_id, history_id=history_id, sender=sender, message_text=message_text)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_recent_messages(db: Session, session_id=None, limit=5):
    query = db.query(Messages).filter(Messages.session_id == session_id).order_by(Messages.timestamp.desc()).limit(limit).all()
    return [(msg.sender, msg.message_text) for msg in query[::-1]]


def get_all_messages(db: Session, skip: int = 0, limit: int = 30):
    return db.query(Messages).filter_by(Messages.timestamp.desc()).offset(skip).limit(limit).all()
