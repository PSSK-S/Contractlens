import os
from sqlalchemy.orm import Session
from .ocr import ocr_pdf_to_text
from .models import Document, PageArtifact

def process_pdf_and_store(db: Session, pdf_path: str, filename: str, langs=("en",)):
    # processed/<doc-stem>/page_000.png, ...
    doc_stem = os.path.splitext(os.path.basename(pdf_path))[0]
    out_dir = os.path.join("processed", doc_stem)
    combined_text, image_paths = ocr_pdf_to_text(pdf_path, out_dir, langs=langs)

    # DB rows
    doc = Document(filename=filename, raw_text=combined_text)
    db.add(doc)
    db.flush()  # get PK

    for idx, img in enumerate(image_paths):
        db.add(PageArtifact(doc_id=doc.doc_id, page_index=idx, image_path=os.path.abspath(img)))

    db.commit()
    db.refresh(doc)
    return doc
