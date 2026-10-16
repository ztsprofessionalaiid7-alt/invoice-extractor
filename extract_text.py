import pdfplumber

def extract_text(path):
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    return "\n".join(pages)

text = extract_text("dev/inv_01.pdf")
print(text)