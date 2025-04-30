import fitz

def extract_text_from_pdf(pdf_data):
    try:
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        text = ""
        
        for page in pdf_document:
            text += page.get_text("text") + "\n"
        
        return text
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

with open("Quantum_Blockchain_Relying_on_Quantum_Secure_Direct_Communication_Network.pdf", "rb") as pdf_file:
    pdf_data = pdf_file.read()

extracted_text = extract_text_from_pdf(pdf_data)
print(extracted_text)
