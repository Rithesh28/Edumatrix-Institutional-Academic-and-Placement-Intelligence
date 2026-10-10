import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

def generate_conference_resubmission_abstract(output_path):
    doc = docx.Document()

    # Standard A4 Page Setup with 1-inch margins
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(0.9)
    section.bottom_margin = Inches(0.9)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

    BLACK = RGBColor(0, 0, 0)
    NAVY = RGBColor(20, 40, 80)
    MUTED = RGBColor(80, 80, 80)

    # Base Normal Style: Times New Roman
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = BLACK

    # 1. Conference Submission Header Tag
    p_top = doc.add_paragraph()
    p_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_top.paragraph_format.space_before = Pt(0)
    p_top.paragraph_format.space_after = Pt(6)
    r_top = p_top.add_run("INTERNATIONAL CONFERENCE SUBMISSION (15th & 16th October, 2026)")
    r_top.font.name = 'Times New Roman'
    r_top.font.size = Pt(8.5)
    r_top.font.bold = True
    r_top.font.color.rgb = MUTED

    # 2. Paper Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(8)
    p_title.paragraph_format.line_spacing = 1.15

    r_title = p_title.add_run("EDUMATRIX: INSTITUTIONAL ACADEMIC AND PLACEMENT INTELLIGENCE SYSTEM")
    r_title.font.name = 'Times New Roman'
    r_title.bold = True
    r_title.font.size = Pt(13)
    r_title.font.color.rgb = NAVY

    # 3. Author Block
    p_auth = doc.add_paragraph()
    p_auth.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_auth.paragraph_format.space_before = Pt(0)
    p_auth.paragraph_format.space_after = Pt(12)
    p_auth.paragraph_format.line_spacing = 1.15

    r_auth = p_auth.add_run("Rithesh N D\n")
    r_auth.font.name = 'Times New Roman'
    r_auth.bold = True
    r_auth.font.size = Pt(10)
    r_auth.font.color.rgb = BLACK

    r_inst = p_auth.add_run("Department of Computer Science and Engineering\nAcademic Research Project")
    r_inst.font.name = 'Times New Roman'
    r_inst.font.italic = True
    r_inst.font.size = Pt(9.5)
    r_inst.font.color.rgb = MUTED

    # 4. Heading: Structured Abstract
    p_head = doc.add_paragraph()
    p_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_head.paragraph_format.space_before = Pt(2)
    p_head.paragraph_format.space_after = Pt(12)

    r_head = p_head.add_run("STRUCTURED ABSTRACT")
    r_head.font.name = 'Times New Roman'
    r_head.bold = True
    r_head.font.size = Pt(11)
    r_head.font.color.rgb = NAVY

    # Helper function for structured section
    def add_structured_section(heading, content, space_after=8):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15

        r_h = p.add_run(heading + ": ")
        r_h.font.name = 'Times New Roman'
        r_h.bold = True
        r_h.font.size = Pt(10)
        r_h.font.color.rgb = BLACK

        r_c = p.add_run(content)
        r_c.font.name = 'Times New Roman'
        r_c.font.size = Pt(10)
        r_c.font.color.rgb = BLACK
        return p

    # EXACT HEADINGS REQUESTED BY THE CONFERENCE:
    # 1. Purpose
    add_structured_section(
        "Purpose",
        "In many higher educational institutions, academic circulars and campus placement notices are shared across multiple decentralized channels like WhatsApp groups, email threads, and physical notice boards. This causes frequent communication gaps, student confusion, and missed deadlines. Furthermore, manually managing placement drives and student records is tedious and prone to delays. This research proposes EDUMATRIX, a centralized, AI-powered academic and placement intelligence platform designed to unify institutional communication, automate administrative notices, and enhance student placement preparedness."
    )

    # 2. Methodology
    add_structured_section(
        "Methodology",
        "EDUMATRIX is implemented using a full-stack reactive architecture with React for the frontend, FastAPI for backend services, PostgreSQL for persistent data management, and Redis with WebSockets for real-time notifications and chat. Role-based access control (RBAC) secures access across student, faculty, and administrator portals. Artificial Intelligence and Natural Language Processing (NLP) models, specifically Named Entity Recognition (NER), are deployed to automatically extract event titles, dates, and deadlines from uploaded PDF circulars. In addition, machine learning modules perform student skill extraction, sentiment analysis, and placement readiness evaluation to recommend suitable job profiles."
    )

    # 3. Findings & Research Implications
    add_structured_section(
        "Findings & Research Implications",
        "System evaluation demonstrates that consolidating academic communication and automating circular processing eliminates message latency and significantly reduces manual overhead for faculty and placement coordinators. Automated date extraction prevents scheduling errors and missed deadlines, while predictive readiness scoring provides objective, data-backed guidance to students. The research implications indicate that educational institutions can transition away from fragmented third-party communication tools to self-hosted, secure, and intelligent institutional management systems."
    )

    # 4. Originality or Novelty of the Study
    add_structured_section(
        "Originality or Novelty of the Study",
        "Unlike conventional academic ERPs or standalone chat applications, EDUMATRIX uniquely integrates real-time institutional communication directly with automated document intelligence (NER-based circular parsing) and placement analytics in a unified, end-to-end framework, establishing a smarter and more organized campus management ecosystem.",
        space_after=12
    )

    # Keywords
    p_kw = doc.add_paragraph()
    p_kw.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_kw.paragraph_format.space_before = Pt(2)
    p_kw.paragraph_format.space_after = Pt(0)
    p_kw.paragraph_format.line_spacing = 1.15

    r_kw_lbl = p_kw.add_run("Keywords: ")
    r_kw_lbl.font.name = 'Times New Roman'
    r_kw_lbl.bold = True
    r_kw_lbl.font.size = Pt(9.5)
    r_kw_lbl.font.color.rgb = NAVY

    r_kw_val = p_kw.add_run(
        "Institutional Intelligence, Academic Management, Placement Readiness, Named Entity Recognition (NER), Machine Learning, FastAPI, WebSockets."
    )
    r_kw_val.font.name = 'Times New Roman'
    r_kw_val.font.size = Pt(9.5)
    r_kw_val.font.color.rgb = BLACK

    doc.save(output_path)
    print(f"Resubmission structured abstract generated at: {output_path}")

if __name__ == "__main__":
    out_file = r"d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EDUMATRIX_Conference_Structured_Abstract.docx"
    generate_conference_resubmission_abstract(out_file)
