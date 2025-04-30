import PyPDF2
import re
import os
import random

def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            text += page.extract_text()
        return text

def extract_questions_with_answers(text):
    # Pattern to match questions with their answers
    # Looking for patterns like: "1. Question text... (1) option1 (2) option2... Ans. (3)"
    pattern = r'(\d+)\.\s+(.*?)\(\d+\)(.*?)Ans\.\s+\((\d+)\)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    questions = []
    for match in matches:
        question_num = match[0]
        question_text = match[1].strip()
        options_text = match[2].strip()
        answer = match[3]
        
        # Extract options
        options_pattern = r'\((\d+)\)\s+(.*?)(?=\(\d+\)|\Z)'
        options = re.findall(options_pattern, options_text, re.DOTALL)
        
        formatted_options = {}
        for opt in options:
            opt_num = opt[0]
            opt_text = opt[1].strip()
            formatted_options[opt_num] = opt_text
        
        questions.append({
            'number': question_num,
            'text': question_text,
            'options': formatted_options,
            'answer': answer
        })
    
    return questions

def create_mock_test(questions, num_questions=30):
    # Select random questions if we have more than requested
    if len(questions) > num_questions:
        selected_questions = random.sample(questions, num_questions)
    else:
        selected_questions = questions
    
    # Format the mock test
    mock_test = "# JEE 2025 Mock Test\n\n"
    answer_key = "# Answer Key\n\n"
    
    for i, q in enumerate(selected_questions, 1):
        mock_test += f"## Question {i}\n"
        mock_test += f"{q['text']}\n\n"
        
        # Add options
        for opt_num, opt_text in q['options'].items():
            mock_test += f"({opt_num}) {opt_text}\n"
        
        mock_test += "\n"
        answer_key += f"Question {i}: ({q['answer']})\n"
    
    return mock_test, answer_key

def main():
    pdf_dir = "./data/Mock/"
    pdf_files = [
        "JEE 2025.pdf",
        "JEE 2025(2).pdf",
        "JEE 2025(3).pdf",
        "JEE 2025(4).pdf"
    ]
    
    all_questions = []
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        print(f"Processing {pdf_file}...")
        
        try:
            text = extract_text_from_pdf(pdf_path)
            questions = extract_questions_with_answers(text)
            
            print(f"Found {len(questions)} questions with answers in {pdf_file}")
            
            # Print a sample question
            if questions:
                sample = questions[0]
                print(f"Sample Question {sample['number']}: {sample['text'][:100]}...")
                print(f"Answer: ({sample['answer']})")
            
            all_questions.extend(questions)
            
        except Exception as e:
            print(f"Error processing {pdf_file}: {str(e)}")
    
    print(f"\nTotal questions found: {len(all_questions)}")
    
    # Create a mock test with 30 questions
    mock_test, answer_key = create_mock_test(all_questions, 30)
    
    # Save the mock test and answer key
    with open("JEE_2025_Mock_Test.md", "w") as f:
        f.write(mock_test)
    
    with open("JEE_2025_Answer_Key.md", "w") as f:
        f.write(answer_key)
    
    print("Mock test and answer key created successfully!")

if __name__ == "__main__":
    main()
