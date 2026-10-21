import io
import pytesseract
from pytesseract import Output
from PIL import Image, ImageDraw

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
for i in range(len(d['text'])):
    t = d['text'][i].strip()
    if t:
        print(f"{t:<22} x={d['left'][i]:<4} y={d['top'][i]:<4} w={d['width'][i]:<4} h={d['height'][i]:<4} line={d['line_num'][i]} par={d['par_num'][i]} block={d['block_num'][i]}")
