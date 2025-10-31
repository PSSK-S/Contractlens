from logging import exception
import os
from sqlalchemy.orm import Session
from .ocr import ocr_pdf_to_text
from .models import Document, PageArtifact
from transformers import pipeline

from typing import Tuple,List


"""
File: pipelines.py
Module: ContractLens
Description: OCR pipeline (Sprint 2) + QA/Summarization (Sprint 3)

Change History:
- 2025-10-15 | v0.3.0 | Satya Pithani | Added QA (/qa) and summarization (/summarize) helpers with chunking.
- 2025-10-10 | v0.2.0 | Satya Pithani | Introduced process_pdf_and_store (PDF→images→EasyOCR) and DB writes.
- 2025-10-03 | v0.1.0 | Satya Pithani | Initial module scaffold.

"""


def process_pdf_and_store(db: Session, pdf_path: str, filename: str, langs=("en",)):

    """
    Converts PDF to images, runs OCR (EasyOCR), stores raw text and page artifacts.
    """

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


# =====================================================================
# Sprint 3 : QA & Summarization
# =====================================================================

#Model names can be overridden via env variables
_QA_Model = os.getenv("QA_MODEL","deepset/roberta-base-squad2")
_Summary_Model = os.getenv("Summary_Model","facebook/bart-large-cnn")

# Lazy sigletons (load once on first call)

_qa_pipe = None
_summary_pipe = None

def _get_qa():
    global _qa_pipe
    if _qa_pipe is None:
        _qa_pipe = pipeline(task="question-answering", model=_QA_Model)
    return _qa_pipe


def _get_summary():
    global _summary_pipe
    if _summary_pipe is None:
        _summary_pipe = pipeline(task='summarization', model=_Summary_Model)
    return _summary_pipe                          


def _split_text(text: str, max_len: int= 1500, overlap: int = 200) -> List[str]:
    """
    Splits text into chunks with specified max length and overlap.

    Args:
        text (str): The input text to split.
        max_len (int): Maximum length of each chunk.
        overlap (int): Number of overlapping characters between chunks.

    Returns:
        List[str]: A list of text chunks.
    """
    text = text or ""
    if len(text) <= max_len:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text),start + max_len)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks    

def answer_question(text: str, question: str) -> Tuple[str, float]:
    """
    Anserrs a question based on the provided text using a QA model
    args:
        text(str): The context text to serach for the answer
        question(str): The question to answer

        returns:
            Tuple[str,float]: The answer and confidence score
    
    """
    qa = _get_qa()
    best_answer = ""
    best_score = 0.0

    for chunk in _split_text(text):
        if not chunk.strip():
            continue
        try:
            res = qa(question=question, context=chunk)
            score = float(res.get("score",0.0))
            ans = (res.get("answer",'')or"").strip()
            if ans and score > best_score:
                best_score = score
                best_answer = ans
        except Exception:
            # ignore chunk errors and continie scanning
            continue

    if best_score < 0:
        return("",0.0)
    return(best_answer, best_score)            

def summarize_text(text: str, max_chunk_chars: int = 2500) -> str:
    """
    summarizes the provider text using a summarization model
    
    args:
        text(str): The text to summarize
        max_chunk_chars(int): Maximum characters per chunk for summarization
        
        returns:
            str: The summarized text

     """
    summarizer = _get_summary()
    chunks  = _split_text(text, max_len=max_chunk_chars, overlap=0)
    if not chunks:
        return ""
    partials = []
    for ch in chunks:
        try:
            out = summarizer(ch, max_length=220,min_lenght=60, do_sample=False,
                             truncation=True)
            partials.append(([0].get("summary_text") or "").strip())
        except Exception:
            #if a single chunk fails, ignore and continue
            continue
    if not partials:
        return ""

    #reduce
    if len(partials) == 1:
        return partials[0]

    merged = "\n".join(partials)
    try:
        final = summarizer(merged,
                           max_lenghth=300,
                           min_length=100,
                           do_sample=False,
                           truncation=True)
        return (final[0].get("summary text")or"").strip()     
    except Exception:
        return merged


