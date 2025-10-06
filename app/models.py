from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, func

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    doc_id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(512))
    vendor = Column(String(256), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    raw_text = Column(Text, nullable=True)

class PageArtifact(Base):
    __tablename__ = "page_artifacts"
    id = Column(Integer, primary_key=True)
    doc_id = Column(Integer, ForeignKey("documents.doc_id", ondelete="CASCADE"), index=True)
    page_index = Column(Integer)  # 0-based
    image_path = Column(String(1024))  # path to rendered PNG
