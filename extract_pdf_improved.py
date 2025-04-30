import PyPDF2
import re
import os

def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            text += page.extract_text()
        return text

def extract_content(pdf_path):
    print(f"Extracting content from {pdf_path}...")
    text = extract_text_from_pdf(pdf_path)
    
    # Print a sample of the text to understand its structure
    print(f"Sample text (first 500 characters):\n{text[:500]}")
    
    # Try to find any patterns that might indicate questions and answers
    # Look for numbers followed by text
    number_pattern = r'\b(\d+)[.)\s]+'
    numbers = re.findall(number_pattern, text)
    print(f"Found {len(numbers)} potential question numbers")
    
    # Look for "ans" or "answer" followed by letters or numbers
    answer_pattern = r'(?:ans|answer)[:\s]*([A-D\d]+)'
    answers = re.findall(answer_pattern, text, re.IGNORECASE)
    print(f"Found {len(answers)} potential answers")
    
    if answers:
        print(f"Sample answers: {answers[:10]}")
    
    return text, numbers, answers

def main():
    pdf_dir = "./data/Mock/"
    pdf_files = [
        "JEE 2025.pdf",
        "JEE 2025(2).pdf",
        "JEE 2025(3).pdf",
        "JEE 2025(4).pdf"
    ]
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        try:
            text, numbers, answers = extract_content(pdf_path)
            print("-" * 50)
        except Exception as e:
            print(f"Error processing {pdf_file}: {str(e)}")

if __name__ == "__main__":
    main()
