from models import Messages, SessionHistory
from db import Session
from sqlalchemy.orm import class_mapper


def model_to_dict(model):
    """Convert a SQLAlchemy model instance into a dictionary."""
    if model is None:
        return None

    columns = [c.key for c in class_mapper(model.__class__).columns]
    return {c: getattr(model, c) for c in columns}


def insert_message(db: Session, history_id, sender, message_text):
    message = Messages(history_id=history_id, sender=sender, message_text=message_text)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def check_and_insert_session(db: Session, session_id, history_id):
    result = db.query(SessionHistory).filter_by(session_id=session_id, history_id=history_id).first()
    if not result:
        insert_history(db, session_id, history_id)


def get_recent_messages(db: Session, history_id=None, limit=6):
    query = db.query(Messages).filter_by(history_id=history_id).order_by(Messages.message_id.desc()).limit(
        limit).all()
    return query[::-1]


def insert_history(db: Session, session_id, history_id):
    history = SessionHistory(session_id=session_id, history_id=history_id)
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def update_history_name(db: Session, session_id, history_id, history_name):
    db.query(SessionHistory).filter_by(session_id=session_id, history_id=history_id).update(
        {"history_name": history_name})
    db.commit()


def get_history_list(db: Session, session_id, skip: int = 0, limit: int = 30):
    return db.query(SessionHistory).filter_by(session_id=session_id).offset(skip).limit(limit).all()


def get_chat_history(db: Session, history_id, skip: int = 0, limit: int = 30):
    return db.query(Messages).filter_by(history_id=history_id).order_by(Messages.message_id).offset(skip).limit(
        limit).all()


def get_all_messages(db: Session, skip: int = 0, limit: int = 30):
    return db.query(Messages).filter_by(Messages.timestamp.desc()).offset(skip).limit(limit).all()


def get_all_history(db: Session, skip: int = 0, limit: int = 30):
    return db.query(SessionHistory).offset(skip).limit(limit).all()
