from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, EmailStr
from typing import Optional
import pandas as pd
import os
from datetime import datetime
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/contact",
    tags=["contact"],
    responses={404: {"description": "Not found"}},
)

# Define the contact form data model
class ContactForm(BaseModel):
    name: str
    email: EmailStr
    exam: str
    message: str

# Path to the Excel file
EXCEL_FILE_PATH = "data/contacts.xlsx"

# Ensure the data directory exists
os.makedirs(os.path.dirname(EXCEL_FILE_PATH), exist_ok=True)

# Function to create Excel file if it doesn't exist
def ensure_excel_file_exists():
    if not os.path.exists(EXCEL_FILE_PATH):
        # Create a new Excel file with headers
        df = pd.DataFrame(columns=["Name", "Email", "Exam", "Message", "Timestamp"])
        df.to_excel(EXCEL_FILE_PATH, index=False)
        logger.info(f"Created new contacts Excel file at {EXCEL_FILE_PATH}")

@router.post("/submit")
async def submit_contact_form(contact_data: ContactForm = Body(...)):
    """
    Submit contact form data and save it to an Excel file
    """
    try:
        # Ensure the Excel file exists
        ensure_excel_file_exists()
        
        # Read existing Excel file
        try:
            df = pd.read_excel(EXCEL_FILE_PATH)
        except Exception as e:
            logger.error(f"Error reading Excel file: {str(e)}")
            # If there's an error reading the file, create a new one
            df = pd.DataFrame(columns=["Name", "Email", "Exam", "Message", "Timestamp"])
        
        # Add new row with current timestamp
        new_row = {
            "Name": contact_data.name,
            "Email": contact_data.email,
            "Exam": contact_data.exam,
            "Message": contact_data.message,
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Append the new row
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Save the updated DataFrame to Excel
        df.to_excel(EXCEL_FILE_PATH, index=False)
        
        logger.info(f"Contact form submission from {contact_data.email} saved to Excel")
        
        return {
            "status": "success",
            "message": "Contact form submitted successfully"
        }
    
    except Exception as e:
        logger.error(f"Error saving contact form data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save contact form data: {str(e)}"
        )
