import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn
import shutil
import os

def set_cell_margins(cell, top=40, bottom=40, left=60, right=60):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def set_table_borders(table, color="D3D3D3", sz="4", val="single"):
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'<w:tblBorders {nsdecls("w")}>'
                        f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
                        f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
                        f'<w:left w:val="none"/>'
                        f'<w:right w:val="none"/>'
                        f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
                        f'<w:insideV w:val="none"/>'
                        f'</w:tblBorders>')
    tblPr.append(borders)

def update_document():
    src_file = "d:/Edumatrix-Institutional-Academic-and-Placement-Intelligence/EDUMATRIX_Research_Paper.docx"
    backup_file = "d:/Edumatrix-Institutional-Academic-and-Placement-Intelligence/EDUMATRIX_Research_Paper_Backup.docx"
    shutil.copyfile(src_file, backup_file)
    
    doc = docx.Document(src_file)
    
    # 1. Update Table 1: Model Comparison
    table1 = doc.tables[0]
    
    # We will clear table1 and populate with compressed data
    # Data structure: 5 rows x 5 cols
    compressed_data = [
        ["Parameter", "Table Transformer", "Resume Parser (LayoutLMv3)", "Intent Classifier (BERT)", "Sentiment Classifier"],
        ["Model Type", "Vision Transformer", "Multimodal Document NLP", "Fine-tuned Transformer", "Deep Learning NLP"],
        ["Train / Test (%)", "96.50 / 94.20", "96.20 / 93.90", "97.80 / 95.60", "95.40 / 93.10"],
        ["Task Focus", "Timetable Extraction", "ATS Resume Parsing", "Query Intent Routing", "Feedback Polarity"],
        ["Key Advantage", "Grid boundary detection", "Multi-column skill parsing", "Fast student query routing", "Accurate sentiment scoring"]
    ]
    
    # Remove excess rows (from 7 down to 5)
    while len(table1.rows) > len(compressed_data):
        tr = table1.rows[-1]._tr
        table1._tbl.remove(tr)
        
    for r_idx, row in enumerate(compressed_data):
        for c_idx, val in enumerate(row):
            cell = table1.cell(r_idx, c_idx)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if (c_idx > 0 or r_idx == 0) else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.0
            r = p.add_run(val)
            r.font.name = "Times New Roman"
            r.font.size = Pt(7.5)
            if r_idx == 0:
                r.bold = True
                cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="F1F5F9"/>'))
            set_cell_margins(cell, top=30, bottom=30, left=40, right=40)
            
    table1.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table1, color="94A3B8", sz="4")
    
    # 2. Locate where to insert Table 2 (Hardware and Software Requirements)
    # In doc, we have paragraph "Workflow Description"
    target_p_idx = -1
    for i, p in enumerate(doc.paragraphs):
        if "Workflow Description" in p.text:
            target_p_idx = i
            break
            
    print(f"Workflow Description found at paragraph {target_p_idx}")
    
    # Insert Table 2 right before Workflow Description
    wf_p = doc.paragraphs[target_p_idx]
    
    # Add a short paragraph introducing System Requirements
    req_heading = wf_p.insert_paragraph_before("Table 2: Hardware and Software Requirements")
    req_heading.paragraph_format.space_before = Pt(4)
    req_heading.paragraph_format.space_after = Pt(2)
    req_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_th = req_heading.runs[0] if req_heading.runs else req_heading.add_run()
    r_th.text = "Table 2: Hardware and Software Requirements"
    r_th.bold = True
    r_th.font.name = "Times New Roman"
    r_th.font.size = Pt(8.5)
    
    # Create Table 2
    # 8 rows x 3 columns
    tbl2_data = [
        ["Component", "Category", "Specification / Tool"],
        ["Hardware", "Processor", "Intel Core i5 / AMD Ryzen 5 or higher"],
        ["", "Memory (RAM)", "8 GB minimum (16 GB recommended)"],
        ["", "Storage", "20 GB SSD available storage"],
        ["Software", "Operating System", "Windows 10/11 or Ubuntu 20.04+"],
        ["", "Frontend", "React.js, Vite, Tailwind CSS, Zustand"],
        ["", "Backend API", "Python 3.10+, FastAPI, WebSockets"],
        ["", "Database & Cache", "PostgreSQL 15, SQLAlchemy, Redis"],
        ["", "AI / ML Frameworks", "PyTorch, HuggingFace, spaCy, OpenCV"]
    ]
    
    table2 = doc.add_table(rows=len(tbl2_data), cols=3)
    table2.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table2, color="94A3B8", sz="4")
    
    for r_idx, row in enumerate(tbl2_data):
        for c_idx, val in enumerate(row):
            cell = table2.cell(r_idx, c_idx)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.0
            r = p.add_run(val)
            r.font.name = "Times New Roman"
            r.font.size = Pt(7.0)
            if r_idx == 0:
                r.bold = True
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="F1F5F9"/>'))
            elif c_idx == 0 and val != "":
                r.bold = True
            set_cell_margins(cell, top=25, bottom=25, left=35, right=35)
            
    # Move Table 2 element before wf_p
    wf_p._p.addprevious(table2._tbl)
    
    output_docx = "d:/Edumatrix-Institutional-Academic-and-Placement-Intelligence/EDUMATRIX_Research_Paper_Updated.docx"
    doc.save(output_docx)
    print("Document successfully updated and saved to", output_docx)

if __name__ == "__main__":
    update_document()
