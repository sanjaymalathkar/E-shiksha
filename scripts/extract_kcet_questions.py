import os
import json
import re
import random
from PyPDF2 import PdfReader

def extract_questions_from_pdf(pdf_path, subject):
    """Extract questions from a PDF file"""
    print(f"Extracting questions from {pdf_path}")
    
    # Read the PDF
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    
    # Split the text into questions
    # This is a simple approach and might need refinement based on the actual PDF structure
    questions_raw = re.split(r'\d+\.\s+', text)[1:]  # Skip the first element which is usually not a question
    
    questions = []
    for i, q_text in enumerate(questions_raw):
        if not q_text.strip():
            continue
            
        # Try to extract options and answer
        options_match = re.findall(r'[A-D]\)\s+(.*?)(?=[A-D]\)|$)', q_text)
        
        if not options_match or len(options_match) < 4:
            print(f"Skipping question {i+1} due to parsing issues")
            continue
        
        # Clean up options
        options = [opt.strip() for opt in options_match[:4]]
        
        # Extract the question text (everything before the first option)
        question_text = q_text.split('A)')[0].strip()
        
        # For demonstration, we'll randomly assign an answer
        # In a real scenario, you'd need to extract the correct answer from the PDF
        correct_answer = random.randint(0, 3)
        
        questions.append({
            "id": len(questions) + 1,
            "exam": "KCET",
            "subject": subject,
            "question": question_text,
            "options": options,
            "answer": correct_answer,
            "explanation": f"This is a sample explanation for the {subject} question."
        })
    
    print(f"Extracted {len(questions)} questions from {pdf_path}")
    return questions

def main():
    # Define the PDF paths
    chemistry_pdf = "data/Mock/KCET-Chemistry.pdf"
    physics_pdf = "data/Mock/KCET-Physics.pdf"
    
    # Extract questions
    chemistry_questions = extract_questions_from_pdf(chemistry_pdf, "Chemistry")
    physics_questions = extract_questions_from_pdf(physics_pdf, "Physics")
    
    # Combine all questions
    all_questions = chemistry_questions + physics_questions
    
    # Shuffle the questions
    random.shuffle(all_questions)
    
    # Limit to a reasonable number (e.g., 50)
    all_questions = all_questions[:50]
    
    # Update the IDs to be sequential
    for i, q in enumerate(all_questions):
        q["id"] = i + 1
    
    # Save to JSON file
    output_path = "app/static/kcet_questions.json"
    with open(output_path, 'w') as f:
        json.dump(all_questions, f, indent=2)
    
    print(f"Saved {len(all_questions)} questions to {output_path}")

if __name__ == "__main__":
    main()
