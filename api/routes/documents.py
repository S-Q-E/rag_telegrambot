from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
import os
from pydantic import BaseModel
from datetime import datetime

from ..retriever import Retriever
from ..db import get_db, User, Document
from ..auth import get_current_user

router = APIRouter()

class DocumentResponse(BaseModel):
    id: int
    filename: str
    upload_date: datetime
    status: str

    class Config:
        orm_mode = True

@router.get("/documents", response_model=List[DocumentResponse])
async def get_documents_list(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Получает список документов, загруженных текущим пользователем.
    """
    documents = db.query(Document).filter(Document.user_id == current_user.id).all()
    return documents

@router.post("/documents")
async def upload_document(
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Загружает новый документ и привязывает его к текущему пользователю.
    """
    retriever = Retriever(db)
    content = await file.read()
    await retriever.add_document(
        file_name=file.filename, 
        content=content.decode("utf-8"), 
        user_id=current_user.id
    )
    return {"filename": file.filename, "owner_id": current_user.id}

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Удаляет документ, если он принадлежит текущему пользователю.
    """
    document = db.query(Document).filter(Document.id == doc_id, Document.user_id == current_user.id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or you don't have permission to delete it")
    db.delete(document)
    db.commit()
    return {"message": "Document deleted"}