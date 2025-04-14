from PIL import Image
import pytesseract
from io import BytesIO

def extract_text(image_data):
    try:
        image = Image.open(BytesIO(image_data))
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        return f"Error extracting text: {str(e)}"

with open("test/Reflection Contest_SENSE.jpg", "rb") as img_file:
    image_data = img_file.read()

text_output = extract_text(image_data)
print(text_output)
