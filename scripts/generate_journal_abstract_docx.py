import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os

def create_journal_abstract_docx(output_path):
    doc = docx.Document()

    # Standard A4 Page Setup with comfortable 1-inch margins
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(1.1)
    section.bottom_margin = Inches(1.1)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

    # Styling Palette
    NAVY = RGBColor(15, 34, 64)       # Professional Dark Navy for Title
    BLACK = RGBColor(20, 20, 20)      # Clean Black for text
    MUTED = RGBColor(70, 70, 70)

    # Base Style
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = BLACK

    # 1. PAPER TITLE (Exact name requested by user)
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(18)
    p_title.paragraph_format.line_spacing = 1.25

    r_title = p_title.add_run("EDUMATRIX - INSTITUTIONAL ACADEMIC AND PLACEMENT INTELLIGENCE SYSTEM")
    r_title.bold = True
    r_title.font.size = Pt(14)
    r_title.font.color.rgb = NAVY

    # Decorative subtle divider
    p_div = doc.add_paragraph()
    p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_div.paragraph_format.space_before = Pt(0)
    p_div.paragraph_format.space_after = Pt(16)
    r_div = p_div.add_run("―" * 28)
    r_div.font.size = Pt(9)
    r_div.font.color.rgb = RGBColor(180, 180, 180)

    # 2. ABSTRACT HEADING
    p_abs = doc.add_paragraph()
    p_abs.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_abs.paragraph_format.space_before = Pt(0)
    p_abs.paragraph_format.space_after = Pt(12)

    r_abs = p_abs.add_run("ABSTRACT")
    r_abs.bold = True
    r_abs.font.size = Pt(11.5)
    r_abs.font.color.rgb = NAVY

    # 3. CLEAN & SIMPLE JOURNAL ABSTRACT PARAGRAPH
    p_body = doc.add_paragraph()
    p_body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_body.paragraph_format.space_before = Pt(0)
    p_body.paragraph_format.space_after = Pt(18)
    p_body.paragraph_format.line_spacing = 1.25

    abstract_text = (
        "In higher educational institutions, administrative communication, academic scheduling, "
        "and student career placement are commonly managed through fragmented and disconnected tools. "
        "This lack of integration frequently results in overlooked academic notices, scheduling "
        "conflicts in faculty examination duties, and limited data-driven support for student placement "
        "readiness. To address these challenges, this paper presents EduMatrix, a unified institutional "
        "intelligence platform engineered to automate academic workflows and enhance student placement "
        "outcomes. The system is built on a decoupled architecture featuring an asynchronous FastAPI "
        "backend, a PostgreSQL relational database, a Qdrant high-dimensional vector database, and a "
        "responsive React web application paired with cross-platform mobile access. The platform unifies "
        "four essential modules: (1) a smart document processing pipeline that extracts text from academic "
        "circulars using OCR, detects important event deadlines via Named Entity Recognition (NER), and "
        "enables fast semantic search using Sentence-Transformers; (2) an automated faculty examination "
        "duty scheduler that utilizes constraint-matching logic to resolve venue and session conflicts "
        "while ensuring balanced workload distribution; (3) an intelligent placement management module "
        "featuring an automated resume analyzer that computes multi-factor ATS compatibility scores, "
        "matches candidate skill profiles against employer job specifications using cosine similarity, "
        "and highlights actionable skill gaps; and (4) a conversational assistant that provides quick, "
        "context-aware answers to student and faculty queries. System evaluation demonstrates sub-second "
        "semantic search retrieval, zero-conflict exam scheduling, and reliable resume-job compatibility "
        "scoring, confirming EduMatrix as an effective, scalable digital governance solution for modern "
        "educational institutions."
    )

    r_body = p_body.add_run(abstract_text)
    r_body.font.size = Pt(11)
    r_body.font.color.rgb = BLACK

    # 4. KEYWORDS
    p_kw = doc.add_paragraph()
    p_kw.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_kw.paragraph_format.space_before = Pt(8)
    p_kw.paragraph_format.space_after = Pt(0)
    p_kw.paragraph_format.line_spacing = 1.20

    r_kw_lbl = p_kw.add_run("Keywords: ")
    r_kw_lbl.bold = True
    r_kw_lbl.font.size = Pt(10)
    r_kw_lbl.font.color.rgb = NAVY

    r_kw_val = p_kw.add_run(
        "Institutional Intelligence, Natural Language Processing, Semantic Vector Search, "
        "Resume Parsing, Applicant Tracking System, Examination Scheduling, FastAPI, Qdrant, "
        "Higher Education Technology."
    )
    r_kw_val.font.size = Pt(10)
    r_kw_val.font.color.rgb = BLACK

    doc.save(output_path)
    print(f"Journal abstract successfully created at: {output_path}")

if __name__ == "__main__":
    out_dir = r"d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence"
    out_file = os.path.join(out_dir, "EduMatrix_Journal_Abstract.docx")
    create_journal_abstract_docx(out_file)
