from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, scoped_session
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/postgres")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = scoped_session(sessionmaker(bind=engine, autocommit=False, autoflush=False))

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, unique=True, index=True)
    messages = relationship("Message", back_populates="user", cascade="all, delete")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String)  # "user" или "bot"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="messages")


def init_db():
    Base.metadata.create_all(bind=engine)


def save_message(chat_id: str, role: str, content: str):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(chat_id=chat_id).first()
        if not user:
            user = User(chat_id=chat_id)
            session.add(user)
            session.commit()
            session.refresh(user)

        msg = Message(user_id=user.id, role=role, content=content)
        session.add(msg)
        session.commit()
    finally:
        session.close()


def get_user_history(chat_id: str, limit: int = 10):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(chat_id=chat_id).first()
        if not user:
            return []
        messages = (
            session.query(Message)
            .filter_by(user_id=user.id)
            .order_by(Message.timestamp.desc())
            .limit(limit)
            .all()
        )
        return messages[::-1]  # хронологический порядок
    finally:
        session.close()
