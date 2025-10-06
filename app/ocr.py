import os
import fitz  # PyMuPDF
import easyocr

def pdf_to_images(pdf_path: str, out_dir: str, dpi: int = 200) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    out_paths = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        img_path = os.path.join(out_dir, f"page_{i:03d}.png")
        pix.save(img_path)
        out_paths.append(img_path)
    doc.close()
    return out_paths

class EasyOCRRunner:
    def __init__(self, langs=("en",)):
        # first run downloads models; allow some time on the first call
        self.reader = easyocr.Reader(langs)

    def image_to_text(self, image_path: str) -> str:
        # detail=0 → only text; paragraph=True merges lines
        result = self.reader.readtext(image_path, detail=0, paragraph=True)
        return "\n".join(result)

def ocr_pdf_to_text(pdf_path: str, out_dir: str, langs=("en",), dpi: int = 200) -> tuple[str, list[str]]:
    image_paths = pdf_to_images(pdf_path, out_dir, dpi=dpi)
    ocr = EasyOCRRunner(langs)
    page_texts = []
    for img in image_paths:
        page_texts.append(ocr.image_to_text(img))
    combined = "\n\n--- PAGE BREAK ---\n\n".join(page_texts)
    return combined, image_paths
