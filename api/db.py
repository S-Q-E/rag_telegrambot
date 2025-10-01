from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func, ForeignKey, JSON
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
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

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    telegram_id = Column(String, unique=True, index=True, nullable=True)
    tariff = Column(String, default='default')
    limits = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
    messages = relationship("Message", back_populates="user")
    documents = relationship("Document", back_populates="owner")

class Document(Base):
    """Модель для хранения документов."""
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    filename = Column(String, index=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="uploaded")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    """Модель для хранения чанков документов в БД."""
    __tablename__ = 'document_chunks'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'))
    assistant_name = Column(String, index=True)
    content = Column(Text)
    embedding = Column(Vector(1536))
    document = relationship("Document", back_populates="chunks")

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
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    assistant = Column(String, index=True)
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    created_at = Column(DateTime, default=func.now())
    user = relationship("User", back_populates="messages")

def save_message(session, chat_id, role, content):
    """Находит пользователя по telegram_id, создает его при необходимости и сохраняет сообщение."""
    user = session.query(User).filter(User.telegram_id == str(chat_id)).first()
    if not user:
        user = User(telegram_id=str(chat_id))
        session.add(user)
        session.commit()
        session.refresh(user)

    msg = Message(user_id=user.id, role=role, content=content)
    session.add(msg)
    session.commit()
