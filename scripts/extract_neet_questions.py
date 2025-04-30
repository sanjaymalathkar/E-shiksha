#!/usr/bin/env python3
"""
Script to extract NEET questions from PDF files and save them as JSON.
"""

import os
import json
import re
import random
import pdfplumber
from pathlib import Path

# Define the paths to the PDF files
BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / "data" / "Mock"
OUTPUT_DIR = BASE_DIR / "app" / "static"

PDF_FILES = {
    "Biology": PDF_DIR / "NEET bio.pdf",
    "Physics": PDF_DIR / "NEET physics.pdf",
    "Chemistry": PDF_DIR / "NEET chemistry.pdf"
}

def extract_questions_from_pdf(pdf_path, subject):
    """Extract questions from a PDF file."""
    questions = []
    question_id = 1
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
            
            # Simple pattern to identify questions (this is a basic approach and might need refinement)
            # Looking for patterns like "1. Question text" followed by options A, B, C, D
            question_blocks = re.split(r'\n\d+\.', text)
            
            for block in question_blocks[1:]:  # Skip the first split which is usually header text
                try:
                    # Extract the question text (everything before the first option)
                    question_match = re.search(r'(.*?)(?:\(A\)|\(a\)|A\.|a\.)', block, re.DOTALL)
                    if not question_match:
                        continue
                    
                    question_text = question_match.group(1).strip()
                    
                    # Extract options
                    options_text = block[question_match.end():].strip()
                    
                    # Try to match options in different formats
                    options_match = re.findall(r'(?:\(([A-D])\)|\b([A-D])\.)\s*(.*?)(?=(?:\([A-D]\)|\b[A-D]\.|\n\d+\.|\Z))', options_text, re.DOTALL)
                    
                    if not options_match or len(options_match) < 4:
                        continue
                    
                    options = []
                    for opt in options_match[:4]:  # Take only the first 4 matches
                        # Use the first non-empty group as the option letter
                        option_text = next(text for text in opt[2:] if text).strip()
                        options.append(option_text)
                    
                    # For this example, we'll randomly assign an answer (in a real scenario, you'd parse the answer key)
                    answer = random.randint(0, 3)
                    
                    questions.append({
                        "id": question_id,
                        "exam": "NEET",
                        "subject": subject,
                        "question": question_text,
                        "options": options,
                        "answer": answer,
                        "explanation": f"This is a sample explanation for the {subject} question."
                    })
                    
                    question_id += 1
                    
                    # Limit to 20 questions per subject for this example
                    if question_id > 20:
                        break
                        
                except Exception as e:
                    print(f"Error processing a question block: {e}")
                    continue
    
    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {e}")
    
    return questions

def main():
    """Main function to extract questions and save them as JSON."""
    all_questions = []
    
    for subject, pdf_path in PDF_FILES.items():
        print(f"Processing {subject} questions from {pdf_path}...")
        subject_questions = extract_questions_from_pdf(pdf_path, subject)
        print(f"Extracted {len(subject_questions)} {subject} questions")
        all_questions.extend(subject_questions)
    
    # Renumber questions to ensure sequential IDs
    for i, question in enumerate(all_questions, 1):
        question["id"] = i
    
    # Save questions to JSON file
    output_path = OUTPUT_DIR / "neet_questions.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(all_questions)} questions to {output_path}")

if __name__ == "__main__":
    main()
