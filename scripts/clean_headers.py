import docx

doc = docx.Document('EDUMATRIX_Research_Paper_Updated.docx')

# Remove "Remove this" in headers
for section in doc.sections:
    header = section.header
    for p in header.paragraphs:
        for r in p.runs:
            if 'Remove this' in r.text:
                r.text = r.text.replace('Remove this', '').strip()
                
    # Check all <w:t> tags in header xml
    for t_node in header._element.xpath('.//w:t'):
        if t_node.text and 'Remove this' in t_node.text:
            print("Found in header <w:t>:", t_node.text)
            t_node.text = t_node.text.replace('Remove this', '').strip()
            
    # Remove text boxes containing 'Remove this' or shapes in header
    for sp_node in header._element.xpath('.//w:drawing | .//w:pict | .//v:shape'):
        txt = "".join(sp_node.itertext())
        if 'Remove this' in txt:
            print("Removing shape with 'Remove this'")
            parent = sp_node.getparent()
            parent.remove(sp_node)

doc.save('EDUMATRIX_Research_Paper_Updated.docx')
print('Header cleaned and saved.')
