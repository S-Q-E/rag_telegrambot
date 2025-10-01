from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
import os
from pydantic import BaseModel
from datetime import datetime

from ..retriever import Retriever, Document
from ..db import get_db

router = APIRouter()

class DocumentResponse(BaseModel):
    id: int
    filename: str
    upload_date: datetime
    status: str

    class Config:
        orm_mode = True

@router.get("/documents", response_model=List[DocumentResponse])
async def get_documents_list(db: Session = Depends(get_db)):
    """
    Получает список всех загруженных документов.
    """
    documents = db.query(Document).all()
    return documents

@router.post("/documents")
async def upload_document(
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    assistant: str = Form(...)
):
    """
    Загружает новый документ.
    """
    retriever = Retriever(db)
    content = await file.read()
    await retriever.add_document(assistant, file.filename, content.decode("utf-8"))
    return {"filename": file.filename}

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """
    Удаляет документ.
    """
    document = db.query(Document).filter(Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(document)
    db.commit()
    return {"message": "Document deleted"}