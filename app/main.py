from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel
import os
import uuid
import shutil

from .db import init_db, get_db
from .pipelines import process_pdf_and_store, answer_question, summarize_text
from .models import Document

"""
File: main.py
App: ContractLens – FastAPI

Change History:
- 2025-10-15 | v0.3.0 | Satya Pithani | Added /qa (POST) and /summarize/{doc_id} (GET); updated app title.
- 2025-10-10 | v0.2.0 | Satya Pithani | Added /upload, /document/{doc_id}, static hosting, health.
- 2025-10-03 | v0.1.0 | Satya Pithani | Project bootstrap with CORS and static mount.
"""


app = FastAPI(title="ContractLens – Sprint 2")



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# serve static assets under /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

load_dotenv()

@app.on_event("startup")
def _startup():
    init_db()

# serve the HTML at GET /
@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/upload")
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # allow PDF/PNG/JPEG; OCR pipeline currently expects PDF (images later if needed)
    if file.content_type not in {"application/pdf", "image/png", "image/jpeg"}:
        raise HTTPException(400, "Only PDF/PNG/JPEG files are allowed")

    # save raw upload
    doc_id = uuid.uuid4().hex
    ext = Path(file.filename).suffix or ".bin"
    saved_name = f"{doc_id}{ext}"
    out_path = UPLOAD_DIR / saved_name
    with out_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # If it's not a PDF, just return saved info (you can add image OCR later)
    if file.content_type != "application/pdf":
        return JSONResponse({
            "doc_id": doc_id,
            "original_filename": file.filename,
            "saved_as": str(out_path.relative_to(BASE_DIR)),
            "content_type": file.content_type,
            "note": "Image uploads stored; PDF OCR is active. Add image OCR later if needed."
        })

    # OCR languages from env (default English)
    langs = tuple([s.strip() for s in os.getenv("OCR_LANGS", "en").split(",") if s.strip()])

    # Run PDF -> images -> OCR -> DB
    doc = process_pdf_and_store(db, str(out_path), file.filename, langs=langs)

    preview = None
    if doc.raw_text:
        preview = doc.raw_text[:1200] + (" ..." if len(doc.raw_text) > 1200 else "")

    return {
        "doc_id": doc.doc_id,
        "filename": doc.filename,
        "saved_as": str(out_path.relative_to(BASE_DIR)),
        "chars": len(doc.raw_text or ""),
        "preview": preview
    }

@app.get("/document/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.doc_id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"doc_id": doc.doc_id, "filename": doc.filename, "raw_text": doc.raw_text}


#====================================================================
# Sprint 3 : QA & Summarization
#====================================================================


class QARequest(BaseModel):
    doc_id: int
    question : str

@app.post("/qa")
def qa_endpoint(payload: QARequest, db: Session = Depends(get_db)):
    """
    Expects Json body with doc_id and question fields.
    arg:
        payload (QARequest): The request payload containing doc_id and question.
        db (Session): Database session dependency.
    Returns:    
        JSONResponse: A JSON response containing the answer to the question.
    Example:
        {
            "doc_id": 1,
            "question": "What is the effective date of the contract?"
        }

    """
    doc = db.query(Document).filter(Document.doc_id == payload.doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    if not doc.raw_text:
        raise HTTPException(status_code=400, detail="No text found in document for performing QA")
    answer, score = answer_question(doc.raw_text, payload.question)
    if not answer:
        return {"doc_id": payload.doc_id, 
                "question": payload.question, 
                "answer": None, 
                "score": 0.0}
    
    return {"doc_id": doc.doc_id,
             "question": payload.question, 
             "answer": answer, 
             "score": score}


@app.get("/Summarize/{doc_id}")
def summarize_endpoint(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.doc_id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not (doc.raw_text and doc.raw_text.strip()):
        raise HTTPException(status_code=400, detail="Document has no OCR text")

    summary = summarize_text(doc.raw_text)
    return {"doc_id": doc_id, "summary": summary}