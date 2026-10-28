import re
query = 'last date to submit ML-II assignment'
tokens = re.findall(r'\b[a-zA-Z0-9_-]{2,}\b', query.lower())
print('Tokens:', tokens)

GENERIC_QUERY_TERMS = {
    'what', 'when', 'where', 'which', 'who', 'whom', 'whose', 'why', 'how',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'the', 'a', 'an', 'and', 'or', 'but', 'if', 'then',
    'else', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into',
    'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from',
    'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'all', 'any',
    'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
    'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'can',
    'could', 'will', 'would', 'should', 'just', 'now', 'tell', 'give', 'show',
    'know', 'please', 'me', 'my', 'our', 'your', 'i', 'we', 'you', 'he', 'she',
    'it', 'they', 'this', 'that', 'these', 'those', 'of', 'there', 'their',
    'want', 'need', 'check', 'find', 'get', 'uploaded', 'upload', 'doc', 'document',
    'today', 'tomorrow', 'yesterday',
    'date', 'dates', 'deadline', 'deadlines', 'last', 'day', 'days', 'time', 'times',
    'submission', 'submissions', 'submit', 'submitting', 'submitted', 'due',
    'due_date', 'duedate',
    'assignment', 'assignments', 'homework', 'task', 'tasks', 'project', 'projects',
    'exam', 'exams', 'examination', 'examinations', 'test', 'tests', 'midterm', 'finals',
    'schedule', 'schedules', 'circular', 'circulars', 'notice', 'notices',
    'info', 'information', 'detail', 'details', 'update', 'updates', 'status'
}
result = [t for t in tokens if t not in GENERIC_QUERY_TERMS]
print('Specific entities:', result)

# Test word boundary matching
title = 'ML-II Assignment'
for e in result:
    match = re.search(rf'\b{re.escape(e)}\b', title.lower())
    print(f'  Matching "{e}" in "{title}": {bool(match)}')

# Also test SQL ILIKE patterns
for e in result:
    escaped = e.replace('%', r'\%').replace('_', r'\_')
    print(f'  Escaped for SQL: {escaped}')
    # ILIKE patterns
    patterns = [
        f"% {escaped} %",
        f"{escaped} %",
        f"% {escaped}",
    ]
    for p in patterns:
        # Check if pattern would match title
        import fnmatch
        match = fnmatch.fnmatch(title.lower(), p.lower().replace('%', '*'))
        print(f'    Pattern "{p}" matches "{title}": {match}')