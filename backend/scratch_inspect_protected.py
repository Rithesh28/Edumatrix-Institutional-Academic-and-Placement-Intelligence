import json

with open('/tmp/placement_cleanup_audit_inventory.json') as f:
    data = json.load(f)

prot = [c for c in data['companies'] if c['classification'] == 'GENUINE_OR_HAS_GENUINE_DEPENDENTS']
student_counts = {}
for c in prot:
    for j in c['jobs']:
        for a in j['applications']:
            if not a['is_test_student']:
                s_key = f"{a['student_id']}: {a['student_email']} ({a['student_name']})"
                student_counts[s_key] = student_counts.get(s_key, 0) + 1

print("Non-test students who have applications in these 53 companies:")
for s, cnt in sorted(student_counts.items(), key=lambda x: -x[1]):
    print(f"  {s}: {cnt} applications")

# Also look at genuine offers
offer_students = {}
for c in prot:
    for j in c['jobs']:
        for o in j['offers']:
            if "test" not in o['student_email']:
                s_key = f"{o['student_id']}: {o['student_email']}"
                offer_students[s_key] = offer_students.get(s_key, 0) + 1

print("\nNon-test students who have placement offers in these 53 companies:")
for s, cnt in sorted(offer_students.items(), key=lambda x: -x[1]):
    print(f"  {s}: {cnt} offers")
