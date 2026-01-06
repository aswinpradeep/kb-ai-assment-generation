import json
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from docx import Document
from docx.shared import Pt, Inches

def generate_pdf(assessment_data: dict, output_path: Path):
    """Generates a PDF report from the assessment JSON data."""
    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Custom Styles
    title_style = styles["Title"]
    h1_style = styles["Heading1"]
    h2_style = styles["Heading2"]
    normal_style = styles["Normal"]
    
    # 1. Title Page
    story.append(Paragraph("Course Assessment Report", title_style))
    story.append(Spacer(1, 12))
    
    blueprint = assessment_data.get("blueprint", {})
    story.append(Paragraph(f"<b>Assessment Scope:</b> {blueprint.get('assessment_scope_summary', 'N/A')}", normal_style))
    story.append(Spacer(1, 12))
    
    # Audit Info
    story.append(Paragraph("<b>Audit Information</b>", h2_style))
    audit_data = [
        ["Prompt Version", blueprint.get("prompt_version", "N/A")],
        ["API Version", blueprint.get("api_version", "N/A")]
    ]
    t = Table(audit_data, colWidths=[150, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 24))

    # 2. Questions Section
    story.append(Paragraph("Questions & Reasoning", h1_style))
    
    questions_obj = assessment_data.get("questions", {})
    
    for q_type, q_list in questions_obj.items():
        story.append(Paragraph(f"{q_type} ({len(q_list)})", h2_style))
        story.append(Spacer(1, 12))
        
        for i, q in enumerate(q_list, 1):
            q_text = q.get("question_text", "N/A")
            story.append(Paragraph(f"<b>Q{i}: {q_text}</b>", normal_style))
            story.append(Spacer(1, 6))
            
            # Options / Details
            if q_type == "Multiple Choice Question":
                for opt in q.get("options", []):
                    story.append(Paragraph(f"- {opt.get('text', '')}", normal_style))
                story.append(Spacer(1, 6))
                story.append(Paragraph(f"<b>Correct Answer:</b> Option {q.get('correct_option_index')}", normal_style))
            
            elif q_type == "MTF Question":
                for p in q.get("pairs", []):
                    story.append(Paragraph(f"- {p.get('left')} -> {p.get('right')}", normal_style))
            
            elif q_type == "Multi-Choice Question":
                for opt in q.get("options", []):
                    story.append(Paragraph(f"[ ] {opt.get('text', '')}", normal_style))
                story.append(Spacer(1, 6))
                corr = q.get('correct_option_index')
                corr_str = ", ".join(map(str, corr)) if isinstance(corr, list) else str(corr)
                story.append(Paragraph(f"<b>Correct Options:</b> {corr_str}", normal_style))

            elif q_type == "True/False Question":
                 story.append(Paragraph(f"- True", normal_style))
                 story.append(Paragraph(f"- False", normal_style))
                 story.append(Spacer(1, 6))
                 story.append(Paragraph(f"<b>Correct Answer:</b> {q.get('correct_answer')}", normal_style))
            
            else:
                story.append(Paragraph(f"<b>Answer:</b> {q.get('correct_answer')}", normal_style))
            
            story.append(Spacer(1, 6))
            
            # Pedagogical Reasoning Box
            reasoning = q.get("reasoning", {})
            kcm = reasoning.get("competency_alignment", {}).get("kcm", {})
            
            reasoning_text = f"""
            <b>Rationale:</b> {reasoning.get('question_type_rationale')}<br/>
            <b>Bloom's Level:</b> {q.get('blooms_level')} ({reasoning.get('blooms_level_justification')})<br/>
            <b>Competency:</b> {kcm.get('competency_area')} - {kcm.get('competency_theme')}<br/>
            <b>Relevance:</b> {q.get('relevance_percentage')}%
            """
            
            # Use a table to create a "box" effect
            r_box = Table([[Paragraph(reasoning_text, styles["BodyText"])]], colWidths=[450])
            r_box.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 1, colors.grey),
                ('BACKGROUND', (0,0), (-1,-1), colors.aliceblue),
                ('PADDING', (0,0), (-1,-1), 8),
            ]))
            story.append(r_box)
            story.append(Spacer(1, 20))
            
        story.append(PageBreak())

    doc.build(story)


def generate_docx(assessment_data: dict, output_path: Path):
    """Generates a DOCX report from the assessment JSON data."""
    doc = Document()
    doc.add_heading('Course Assessment Report', 0)

    blueprint = assessment_data.get("blueprint", {})
    doc.add_paragraph(f"Assessment Scope: {blueprint.get('assessment_scope_summary', 'N/A')}")
    
    # Audit Table
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Field'
    hdr_cells[1].text = 'Value'
    
    row_cells = table.add_row().cells
    row_cells[0].text = 'Prompt Version'
    row_cells[1].text = str(blueprint.get("prompt_version", "N/A"))
    
    row_cells = table.add_row().cells
    row_cells[0].text = 'API Version'
    row_cells[1].text = str(blueprint.get("api_version", "N/A"))
    
    doc.add_heading('Questions & Reasoning', level=1)
    
    questions_obj = assessment_data.get("questions", {})
    
    for q_type, q_list in questions_obj.items():
        doc.add_heading(f"{q_type} ({len(q_list)})", level=2)
        
        for i, q in enumerate(q_list, 1):
            doc.add_paragraph(f"Q{i}: {q.get('question_text', 'N/A')}", style='List Number')
            
            if q_type == "Multiple Choice Question":
                for opt in q.get("options", []):
                    doc.add_paragraph(f"- {opt.get('text', '')}", style='List Bullet')
                p = doc.add_paragraph()
                p.add_run(f"Correct Answer: Option {q.get('correct_option_index')}").bold = True
            
            elif q_type == "MTF Question":
                for p_item in q.get("pairs", []):
                    doc.add_paragraph(f"- {p_item.get('left')} -> {p_item.get('right')}", style='List Bullet')

            elif q_type == "Multi-Choice Question":
                for opt in q.get("options", []):
                     doc.add_paragraph(f"[ ] {opt.get('text', '')}", style='List Bullet')
                p = doc.add_paragraph()
                corr = q.get('correct_option_index')
                corr_str = ", ".join(map(str, corr)) if isinstance(corr, list) else str(corr)
                p.add_run(f"Correct Options: {corr_str}").bold = True

            elif q_type == "True/False Question":
                 doc.add_paragraph(f"- True", style='List Bullet')
                 doc.add_paragraph(f"- False", style='List Bullet')
                 p = doc.add_paragraph()
                 p.add_run(f"Correct Answer: {q.get('correct_answer')}").bold = True
            
            else:
                 p = doc.add_paragraph()
                 p.add_run(f"Answer: {q.get('correct_answer')}").bold = True

            # Reasoning
            reasoning = q.get("reasoning", {})
            kcm = reasoning.get("competency_alignment", {}).get("kcm", {})
            
            r_para = doc.add_paragraph()
            r_para.add_run(f"\nRationale: {reasoning.get('question_type_rationale')}\n").italic = True
            r_para.add_run(f"Bloom's: {q.get('blooms_level')} | Relevance: {q.get('relevance_percentage')}%\n")
            r_para.add_run(f"Competency: {kcm.get('competency_area')} - {kcm.get('competency_theme')}")
            
    doc.save(str(output_path))
