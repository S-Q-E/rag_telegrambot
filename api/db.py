from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("POSTGRES_DB")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Message(Base):
    """Модель для хранения истории сообщений."""
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True)
    assistant = Column(String, index=True)
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    created_at = Column(DateTime, default=func.now())

async def save_message(session, chat_id, role, content):
    user = session.query(User).filter_by(chat_id=chat_id).first()
    if not user:
        user = User(chat_id=chat_id)
        session.add(user)
        session.commit()
        session.refresh(user)

    msg = Message(user_id=user.id, role=role, content=content)
    session.add(msg)
    session.commit()
