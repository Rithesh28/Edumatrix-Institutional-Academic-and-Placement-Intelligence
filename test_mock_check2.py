with open('D:/Edumatrix-Institutional-Academic-and-Placement-Intelligence/backend/tests/unit/test_circular_authz.py', 'r') as f:
    content = f.read()
# Check all mock modules are present - using the exact format from the file
import re
# Find all lines with sys.modules[_mod] = MagicMock
matches = re.findall(r'sys\.modules\[_mod\] = MagicMock', content)
print(f'Found {len(matches)} mock assignments')
# Show the actual _mod values by extracting the string literals
mod_pattern = re.findall(r'\"([^\"]+)\"', content)
print(f'String literals found: {len(mod_pattern)}')
# Show first 15
for m in mod_pattern[:15]:
    print(f'  - {m}')
# Check for pdfplumber
if 'pdfplumber' in content:
    # Find where
    idx = content.index('pdfplumber')
    print(f'\\npdfplumber found at position {idx}: ...{content[idx:idx+50]}...')
else:
    print('\\nNo pdfplumber references')