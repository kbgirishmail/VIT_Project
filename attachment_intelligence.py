# attachment_intelligence.py
import os
import pytesseract
from PIL import Image
import fitz
from io import BytesIO
from docx import Document # type: ignore

def extract_text_from_image(image_data):
    """Extract text from image binary."""
    try:
        image = Image.open(BytesIO(image_data))
        return pytesseract.image_to_string(image)
    except Exception as e:
        return f"Error extracting text from image: {str(e)}"

def extract_text_from_pdf(pdf_data):
    """Extract text from PDF binary."""
    try:
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        return "\n".join([page.get_text("text") for page in pdf_document])
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

def extract_text_from_docx(docx_data):
    """Extract text from Word (.docx) binary."""
    try:
        with open("temp.docx", "wb") as f:
            f.write(docx_data)
        document = Document("temp.docx")
        os.remove("temp.docx")
        return "\n".join([para.text for para in document.paragraphs])
    except Exception as e:
        return f"Error extracting text from DOCX: {str(e)}"

# Example attachment scanner
def scan_attachment(file_name, binary_data):
    """Determine attachment type and extract text for tagging."""
    ext = os.path.splitext(file_name)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png']:
        return extract_text_from_image(binary_data)
    elif ext == '.pdf':
        return extract_text_from_pdf(binary_data)
    elif ext == '.docx':
        return extract_text_from_docx(binary_data)
    else:
        return "Unsupported attachment type."

# Example Usage:
# with open("sample.pdf", "rb") as f:
#     print(scan_attachment("sample.pdf", f.read()))
