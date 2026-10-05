from io import BytesIO

from fastapi import UploadFile
from pypdf import PdfReader
from docx import Document

async def extract_pdf_text(file: UploadFile) -> str:
    content = await file.read()
    reader = PdfReader(BytesIO(content))
    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text

async def extract_docx_text(file: UploadFile) -> str:
    content = await file.read()
    document = Document(BytesIO(content))
    text = ""

    for paragraph in document.paragraphs:
        if paragraph.text:
            text += paragraph.text + "\n"

    return text

async def extract_attachment_text(file: UploadFile) -> str:
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        return await extract_pdf_text(file)

    if filename.endswith(".docx"):
        return await extract_docx_text(file)

    return ""