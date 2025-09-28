from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uuid, shutil

app = FastAPI(title="ContractLens – Sprint 1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ✅ serve static assets under /static (not /)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ✅ serve the HTML at GET /
@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    if file.content_type not in {"application/pdf", "image/png", "image/jpeg"}:
        raise HTTPException(400, "Only PDF/PNG/JPEG files are allowed")
    doc_id = uuid.uuid4().hex
    ext = Path(file.filename).suffix or ".bin"
    out_path = UPLOAD_DIR / f"{doc_id}{ext}"
    with out_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return JSONResponse({
        "doc_id": doc_id,
        "original_filename": file.filename,
        "saved_as": str(out_path.relative_to(BASE_DIR)),
        "content_type": file.content_type
    })
