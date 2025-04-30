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

def extract_questions_and_answers(text):
    # Pattern to find questions and answers
    # This is a simple pattern and might need adjustment based on the actual PDF format
    question_pattern = r'Q(\d+)[.\s]+(.*?)(?=Q\d+|\Z)'
    questions = re.findall(question_pattern, text, re.DOTALL)
    
    # Pattern to find answers marked as "ans"
    answer_pattern = r'ans[:\s]*([A-D])'
    answers = re.findall(answer_pattern, text, re.IGNORECASE)
    
    return questions, answers

def main():
    pdf_dir = "./data/Mock/"
    pdf_files = [
        "JEE 2025.pdf",
        "JEE 2025(2).pdf",
        "JEE 2025(3).pdf",
        "JEE 2025(4).pdf"
    ]
    
    all_questions = []
    all_answers = []
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        print(f"Processing {pdf_file}...")
        
        try:
            text = extract_text_from_pdf(pdf_path)
            questions, answers = extract_questions_and_answers(text)
            
            print(f"Found {len(questions)} questions and {len(answers)} answers in {pdf_file}")
            
            # Print first few questions and answers as a sample
            for i in range(min(3, len(questions))):
                print(f"Q{questions[i][0]}: {questions[i][1][:100]}...")
            
            if answers:
                print(f"Sample answers: {answers[:5]}")
            
            all_questions.extend(questions)
            all_answers.extend(answers)
            
        except Exception as e:
            print(f"Error processing {pdf_file}: {str(e)}")
    
    print(f"\nTotal questions found: {len(all_questions)}")
    print(f"Total answers found: {len(all_answers)}")

if __name__ == "__main__":
    main()
