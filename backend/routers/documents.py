import os
import shutil
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from database import get_db
from models import User, Document
from schemas import DocumentResponse
from dependencies import get_current_user
from retriever import add_document_to_index, add_summary_to_index, vectorstore, summary_vectorstore
from nodes import summarize_document

router = APIRouter(prefix="/documents", tags=["Documents"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Upload a document
@router.post("/upload", response_model=DocumentResponse)
def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    # Save the file to disk with a unique name to avoid overwrites
    safe_filename = f"{current_user.id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Index the document into the vector store so retrieval can find it
    try:
        add_document_to_index(file_path, file.filename)
        summary = summarize_document(file.filename)
        add_summary_to_index(file.filename, summary)
    except Exception as e:
        print(f"Warning: failed to index {file.filename}: {e}")

    # Save metadata to the database
    new_document = Document(
        filename=file.filename,
        filepath=file_path,
        owner_id=current_user.id
    )
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    return new_document

# List documents — admin sees all, regular user sees only their own
@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "admin":
        return db.query(Document).all()
    return db.query(Document).filter(Document.owner_id == current_user.id).all()

# Analytics — document counts and upload activity for charts
@router.get("/stats")
def get_document_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Base query — admin sees stats across all users, regular user sees only their own
    base_query = db.query(Document)
    if current_user.role != "admin":
        base_query = base_query.filter(Document.owner_id == current_user.id)

    total_documents = base_query.count()

    # Documents uploaded per day, over the last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    daily_counts = (
        base_query
        .filter(Document.uploaded_at >= seven_days_ago)
        .with_entities(
            func.date(Document.uploaded_at).label("date"),
            func.count(Document.id).label("count")
        )
        .group_by(func.date(Document.uploaded_at))
        .order_by(func.date(Document.uploaded_at))
        .all()
    )
    upload_history = [{"date": str(row.date), "count": row.count} for row in daily_counts]

    # Documents per user — admin only, since regular users only have their own anyway
    documents_per_user = []
    if current_user.role == "admin":
        per_user = (
            db.query(User.full_name, func.count(Document.id).label("count"))
            .join(Document, Document.owner_id == User.id)
            .group_by(User.full_name)
            .all()
        )
        documents_per_user = [{"user": row.full_name, "count": row.count} for row in per_user]

    return {
        "total_documents": total_documents,
        "upload_history": upload_history,
        "documents_per_user": documents_per_user,
    }

# Delete a document — only the owner or an admin can delete it
@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete this document"
        )

    # Delete the physical file from disk
    if os.path.exists(document.filepath):
        os.remove(document.filepath)

    # Also remove this document's chunks and its hierarchical-retrieval summary
    # from the vector stores. Previously only the SQL row and the on-disk file
    # were removed, so a "deleted" document's chunks and summary stayed in
    # chroma_db/chroma_summaries_db forever - still able to influence retrieval
    # and document-routing for completely unrelated future questions.
    try:
        vectorstore._collection.delete(where={"source": document.filename})
        summary_vectorstore._collection.delete(where={"source": document.filename})
    except Exception as e:
        print(f"Warning: failed to remove {document.filename} from vector stores: {e}")

    db.delete(document)
    db.commit()
    return {"detail": "Document deleted successfully"}

@router.get("/{document_id}/summary")
def get_document_summary(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view this document"
        )

    summary = summarize_document(document.filename)
    return {"filename": document.filename, "summary": summary}