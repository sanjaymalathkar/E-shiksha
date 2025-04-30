import os
import logging
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.units import inch

# Set up logging
logger = logging.getLogger(__name__)

def generate_pdf_from_analysis(
    analysis_result: Dict[str, Any],
    exam_type: Optional[str] = None,
    title: Optional[str] = None,
    output_path: Optional[str] = None
) -> str:
    """
    Generate a PDF document from Ollama analysis results

    Args:
        analysis_result: The analysis result from Ollama
        exam_type: Type of exam (optional)
        title: Title for the PDF (optional)
        output_path: Path to save the PDF (optional, will use temp file if not provided)

    Returns:
        Path to the generated PDF file
    """
    try:
        # Create a temporary file if output_path is not provided
        if not output_path:
            # Create data/pdf directory if it doesn't exist
            pdf_dir = os.path.join("data", "pdf")
            os.makedirs(pdf_dir, exist_ok=True)

            # Generate a filename based on timestamp and exam type
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            exam_suffix = f"_{exam_type}" if exam_type else ""
            output_path = os.path.join(pdf_dir, f"analysis_{timestamp}{exam_suffix}.pdf")

        # Create the PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Get styles
        styles = getSampleStyleSheet()

        # Create custom styles with colors matching the UI
        # Use indigo color to match the UI
        indigo_color = colors.Color(0.38, 0.39, 0.96)  # Indigo color similar to the UI

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            spaceAfter=12,
            textColor=indigo_color,
            alignment=1  # Center alignment
        )

        heading1_style = ParagraphStyle(
            'Heading1',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=10,
            textColor=indigo_color
        )

        heading2_style = ParagraphStyle(
            'Heading2',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=8,
            textColor=indigo_color
        )

        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=6
        )

        bullet_style = ParagraphStyle(
            'BulletStyle',
            parent=normal_style,
            leftIndent=20,
            firstLineIndent=0
        )

        # Create the content elements
        elements = []

        # Add title
        pdf_title = title if title else "Educational Content Analysis"
        if exam_type:
            pdf_title += f" - {exam_type}"
        elements.append(Paragraph(pdf_title, title_style))

        # Add date
        date_str = datetime.now().strftime("%B %d, %Y")
        elements.append(Paragraph(f"Generated on: {date_str}", styles['Italic']))
        elements.append(Spacer(1, 0.25*inch))

        # Add a logo or header image if available
        try:
            logo_path = "app/static/images/logo.png"
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=2*inch, height=0.75*inch)
                elements.append(logo)
                elements.append(Spacer(1, 0.25*inch))
        except Exception as e:
            logger.warning(f"Could not add logo: {str(e)}")

        # Add analysis content
        if "result" in analysis_result and analysis_result["result"]:
            content = analysis_result["result"]

            # Split content by headings for better formatting
            # This is a simple approach - for more complex formatting,
            # we would need to parse the content more carefully
            lines = content.split("\n")

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                if not line:
                    i += 1
                    continue

                # Check if this is a heading
                if line.startswith("# "):
                    # Main heading
                    heading_text = line.replace("# ", "").strip()
                    elements.append(Paragraph(heading_text, heading1_style))
                    elements.append(Spacer(1, 0.1*inch))
                elif line.startswith("## "):
                    # Subheading
                    heading_text = line.replace("## ", "").strip()
                    elements.append(Paragraph(heading_text, heading2_style))
                    elements.append(Spacer(1, 0.05*inch))
                elif line.startswith("### "):
                    # Sub-subheading
                    heading_text = line.replace("### ", "").strip()
                    elements.append(Paragraph(heading_text, heading2_style))
                    elements.append(Spacer(1, 0.05*inch))
                elif line.startswith("- ") or line.startswith("* "):
                    # Collect all bullet points in a sequence
                    bullets = []
                    while i < len(lines) and (lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")):
                        bullet_text = lines[i].strip().replace("- ", "").replace("* ", "").strip()
                        bullets.append(f"• {bullet_text}")
                        i += 1

                    # Add each bullet point
                    for bullet in bullets:
                        elements.append(Paragraph(bullet, bullet_style))

                    # Add a small space after the bullet list
                    elements.append(Spacer(1, 0.1*inch))

                    # Continue from the current position (don't increment i again)
                    continue
                else:
                    # Regular paragraph - collect consecutive non-bullet, non-heading lines
                    paragraph_lines = [line]
                    j = i + 1
                    while j < len(lines) and lines[j].strip() and not lines[j].strip().startswith(("#", "-", "*")):
                        paragraph_lines.append(lines[j].strip())
                        j += 1

                    # Join the paragraph lines and add as a single paragraph
                    paragraph_text = " ".join(paragraph_lines)
                    elements.append(Paragraph(paragraph_text, normal_style))
                    elements.append(Spacer(1, 0.1*inch))

                    # Update i to the next line after the paragraph
                    i = j - 1

                i += 1

        # Add metadata
        elements.append(PageBreak())
        elements.append(Paragraph("Analysis Metadata", heading1_style))
        elements.append(Spacer(1, 0.1*inch))

        # Create a table for metadata with UI-matching colors
        metadata = [
            ["Files Processed", str(analysis_result.get("files_processed", "N/A"))],
            ["Exam Type", exam_type if exam_type else "Not specified"],
            ["Analysis Date", date_str],
            ["Analysis Status", analysis_result.get("status", "N/A")]
        ]

        # Add more metadata if available
        if "model" in analysis_result:
            metadata.append(["Model Used", analysis_result.get("model", "N/A")])

        # Create the table with UI-matching colors
        metadata_table = Table(metadata, colWidths=[2*inch, 3*inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.Color(0.95, 0.95, 1.0)),  # Light indigo background
            ('TEXTCOLOR', (0, 0), (0, -1), indigo_color),  # Indigo text color
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.Color(0.8, 0.8, 0.95)),  # Light indigo grid
            ('ROUNDEDCORNERS', [5, 5, 5, 5]),  # Rounded corners
        ]))

        elements.append(metadata_table)

        # Add footer with disclaimer and branding
        elements.append(Spacer(1, 0.5*inch))

        # Create a custom style for the footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Italic'],
            fontSize=8,
            textColor=colors.gray,
            alignment=1  # Center alignment
        )

        # Add disclaimer
        disclaimer = "This document was automatically generated based on AI analysis of educational content. " \
                    "The analysis may not be comprehensive and should be reviewed by an educator."
        elements.append(Paragraph(disclaimer, footer_style))

        # Add branding
        elements.append(Spacer(1, 0.1*inch))
        branding = "Generated by E-Shiksha Educational Content Analysis System"
        elements.append(Paragraph(branding, footer_style))

        # Add page numbers
        def add_page_number(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(colors.gray)
            page_num = canvas.getPageNumber()
            text = f"Page {page_num}"
            canvas.drawRightString(doc.pagesize[0] - 30, 30, text)
            canvas.restoreState()

        # Build the PDF with page numbers
        doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)

        logger.info(f"Generated PDF at {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise
