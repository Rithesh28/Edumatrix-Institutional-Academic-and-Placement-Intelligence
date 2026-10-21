import io
import re
import statistics
import pytesseract
from pytesseract import Output
from PIL import Image, ImageDraw

def test_spatial_parser():
    # Create the test image
    img = Image.new('RGB', (800, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    rows = [
        ['4VP23AI002', 'Adithya CS', 'adi01@gmail.com', 'Selected'],
        ['4VP23CS045', 'Bhavya Rao', 'bhavya@gmail.com', 'Shortlisted'],
        ['4VP23IS012', 'Chetan Kumar', 'chetan@gmail.com', 'Rejected'],
    ]
    draw.text((30, 30), 'CAMPUS RECRUITMENT SHORTLIST - 2026', fill=(0, 0, 0))
    draw.text((30, 70), 'USN                 Name               Email                    Status', fill=(0, 0, 0))
    y = 100
    for i, r in enumerate(rows):
        line_str = f'{r[0]:<18}  {r[1]:<16}  {r[2]:<22}  {r[3]}'
        draw.text((30, y + i * 30), line_str, fill=(0, 0, 0))

    d = pytesseract.image_to_data(img, output_type=Output.DICT)

    # 1. Collect valid word tokens
    tokens = []
    for i in range(len(d['text'])):
        word = str(d['text'][i]).strip()
        if not word or word in ["|", "~", "^", "—", "_", "`"]:
            continue
        conf = float(d['conf'][i]) if 'conf' in d and d['conf'][i] != -1 else 50.0
        left = int(d['left'][i])
        top = int(d['top'][i])
        w = int(d['width'][i])
        h = int(d['height'][i])
        tokens.append({
            "text": word, "left": left, "top": top,
            "right": left + w, "bottom": top + h,
            "width": w, "height": h,
            "conf": conf,
            "center_x": left + w / 2, "center_y": top + h / 2
        })

    # 2. Cluster into visual rows
    med_h = statistics.median([t['height'] for t in tokens]) if tokens else 10
    y_tol = max(8, int(med_h * 0.6))
    tokens.sort(key=lambda t: (t['top'], t['left']))

    v_rows = []
    for t in tokens:
        matched_row = None
        for r in v_rows:
            if abs(t['center_y'] - r['avg_y']) <= y_tol:
                matched_row = r
                break
        if matched_row:
            matched_row['tokens'].append(t)
            matched_row['min_top'] = min(matched_row['min_top'], t['top'])
            matched_row['max_bottom'] = max(matched_row['max_bottom'], t['bottom'])
            matched_row['avg_y'] = sum(tok['center_y'] for tok in matched_row['tokens']) / len(matched_row['tokens'])
        else:
            v_rows.append({
                'tokens': [t],
                'min_top': t['top'],
                'max_bottom': t['bottom'],
                'avg_y': t['center_y']
            })

    for r in v_rows:
        r['tokens'].sort(key=lambda t: t['left'])
        r['text'] = " ".join(t['text'] for t in r['tokens'])

    print(f"Tokens collected: {len(tokens)}")
    for t in tokens:
        print(f"  {t['text']:<25} conf={t['conf']} top={t['top']} left={t['left']}")

    print(f"\nTotal visual rows detected: {len(v_rows)}")
    for i, r in enumerate(v_rows):
        print(f"  Row {i}: y={int(r['avg_y'])}: '{r['text']}'")

if __name__ == "__main__":
    test_spatial_parser()
