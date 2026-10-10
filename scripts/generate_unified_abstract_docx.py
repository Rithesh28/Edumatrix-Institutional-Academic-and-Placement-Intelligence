import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

def generate_unified_abstract(output_path):
    doc = docx.Document()

    # Standard A4 Page Setup with clean 1-inch margins
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

    BLACK = RGBColor(0, 0, 0)

    # Base Style: Times New Roman
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = BLACK

    # 1. Project Title (Centered, Bold, Academic 14pt)
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(14)
    p_title.paragraph_format.line_spacing = 1.2

    r_title = p_title.add_run("EDUMATRIX: INSTITUTIONAL ACADEMIC AND PLACEMENT INTELLIGENCE SYSTEM")
    r_title.font.name = 'Times New Roman'
    r_title.bold = True
    r_title.font.size = Pt(14)
    r_title.font.color.rgb = BLACK

    # 2. Heading: ABSTRACT (Centered, Bold, 12pt)
    p_head = doc.add_paragraph()
    p_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_head.paragraph_format.space_before = Pt(6)
    p_head.paragraph_format.space_after = Pt(18)

    r_head = p_head.add_run("ABSTRACT")
    r_head.font.name = 'Times New Roman'
    r_head.bold = True
    r_head.font.size = Pt(12.5)
    r_head.font.color.rgb = BLACK

    # 3. Unified Single-Paragraph Abstract Body
    p_body = doc.add_paragraph()
    p_body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_body.paragraph_format.space_before = Pt(0)
    p_body.paragraph_format.space_after = Pt(18)
    p_body.paragraph_format.line_spacing = 1.35  # Formal 1.35x academic line spacing

    abstract_text = (
        "In contemporary higher educational institutions, critical academic schedules, notices, and recruitment "
        "updates remain fragmented across disparate informal channels such as messaging groups, email chains, and "
        "physical notice boards, leading to communication bottlenecks, missed student deadlines, and labor-intensive "
        "placement administration. To address these challenges, this project introduces EDUMATRIX, a centralized, "
        "AI-powered Institutional Academic and Placement Intelligence System designed to streamline administrative "
        "workflows and automate student career readiness. The platform is architected using a reactive full-stack "
        "framework comprising React, FastAPI, PostgreSQL, Redis, and WebSockets, enforcing strict role-based access "
        "control across student, lecturer, and administrator dashboards. Artificial Intelligence and Natural Language "
        "Processing pipelines are embedded into the system, incorporating Named Entity Recognition (NER) to "
        "automatically extract event titles, schedules, and deadlines from uploaded PDF circulars, alongside models "
        "for intent classification, sentiment analysis, placement readiness prediction, and skill-to-company matching. "
        "Findings from system deployment show that automated document ingestion and real-time WebSocket broadcasting "
        "substantially eliminate communication latency and manual coordination overhead, while delivering objective, "
        "data-driven readiness metrics that enhance student recruitment outcomes. Although the current implementation "
        "is evaluated within an institutional environment using standard circular templates, it establishes an "
        "extensible foundation for future multi-campus federations and multilingual document processing. EDUMATRIX "
        "demonstrates significant originality and practical value by bridging real-time campus collaboration with "
        "automated document intelligence and predictive placement analytics within a unified, technology-driven academic "
        "ecosystem."
    )

    r_body = p_body.add_run(abstract_text)
    r_body.font.name = 'Times New Roman'
    r_body.font.size = Pt(11.5)
    r_body.font.color.rgb = BLACK

    # 4. Keywords
    p_kw = doc.add_paragraph()
    p_kw.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_kw.paragraph_format.space_before = Pt(6)
    p_kw.paragraph_format.space_after = Pt(0)
    p_kw.paragraph_format.line_spacing = 1.2

    r_kw_lbl = p_kw.add_run("Keywords: ")
    r_kw_lbl.font.name = 'Times New Roman'
    r_kw_lbl.bold = True
    r_kw_lbl.font.size = Pt(11)
    r_kw_lbl.font.color.rgb = BLACK

    r_kw_val = p_kw.add_run(
        "Institutional Intelligence, Academic Management, Placement Readiness, Named Entity Recognition (NER), Machine Learning, FastAPI, WebSockets, Skill Matching."
    )
    r_kw_val.font.name = 'Times New Roman'
    r_kw_val.font.size = Pt(11)
    r_kw_val.font.color.rgb = BLACK

    doc.save(output_path)
    print(f"Unified single-paragraph abstract generated at: {output_path}")

if __name__ == "__main__":
    out_file = r"d:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\EDUMATRIX_Single_Paragraph_Abstract.docx"
    generate_unified_abstract(out_file)
