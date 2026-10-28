import re

# Test SQL wildcard escaping for various entity types
test_entities = [
    "ml",          # simple acronym
    "ml-ii",       # with hyphen
    "dsp",         # simple acronym
    "c++",         # with special chars
    "100%",        # contains % wildcard
    "test_case",   # contains _ wildcard
    "ai/ml",       # contains /
    "oop's",       # contains apostrophe
]

for e in test_entities:
    escaped = e.replace('%', r'\%').replace('_', r'\_')
    print(f'Original: "{e}" -> Escaped: "{escaped}"')
    # Show the ILIKE patterns that would be generated
    patterns = [
        f"% {escaped} %",
        f"{escaped} %",
        f"% {escaped}",
    ]
    print(f'  Patterns: {patterns}')
    print()