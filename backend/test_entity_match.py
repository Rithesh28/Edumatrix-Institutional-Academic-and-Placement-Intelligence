from app.services.institutional_retrieval_service import institutional_retrieval_service
import re

query = 'When is DLRL CIE 2 exam'
entities = institutional_retrieval_service.extract_specific_entities(query)
print(f'Entities: {entities}')

# Check what the specific entities match in the circular content
circular_content = """--- Page 1 ---
Vivekananda College of Engineering & Technology tie hectic

Affiliated to Visvesvaraya Technological University, Approved by AICTE New Delhi & Govt of Karnataka ExamCell
26/08/26

SEVENTH SEMESTER CIE EXAMINATION TIME TABLE -- 2022 SCHEME

First CIE :- 10, 11 & 12 September 2026 Second CIE :- 04, 05 & 06 November 2026
MORNING SESSION -- 9.30 AM TO 11.00 AM AFTERNOON SESSION -- 03.00 PM TO 4.30 PM
Course 3 ; Course . .
Type Course Code Subject Title Type Course Code Subjec

| IPCC BAI701 | DEEP LEARNING & REINFORCEMENT LEARNING | | BAI702 MACHINE LEARNING-II
| | |
| | STATISTICAL MACHINE LEARNING FOR
7. CD) IPCC | Pp 2
| \ IPCC BDS70 PARALLEL PROGRAMMING 7 CD IPCC BAD702 DATA SCIENCE
7. CS | IPCC | _BCS70 | INTERNET OF THINGS 7 | cs IPCC BCS702. | PARALLEL COMPUTING |
. | | | ESTIMATION AND CONTRACT |
5 H | | aval | > |
7 CV IPCC BCV70 DESIGN OF STEEL STRUCTURE 7 CV | IPCC BCV702 MANAGEMENT
i : |
| ap | ye, MICROWAVE ENGINEERING AND ANTENNA aes _ 4 COMPUTER NETWORKS AND i
7 | EC IPCC BEC701 THEORY 7 EC IPCC BEC702 PROTOCOLS
7 ME | IPCC BME70 | FINITE ELEMENT METHODS | 7 ME | IPCC | ~BME702 ~HYDRAULICS & PNEUMATICS |

MORNING SESSION - 9.30 AM TO 11.00 AM AFTERNOON SESSION -- 03.00 PM TO 4.30 PM

Course
Type

Course

Sem BE a Course Code Subject Title
Type

Course Code Subject Title

| BAD703. | DATA SECURITY & PRIVACY 7 | AL | PEC BAD714B BUSINESS ANALYTICS |
"""
content_lower = circular_content.lower()
for e in entities:
    match = re.search(rf'\b{re.escape(e)}\b', content_lower)
    print(f'Entity "{e}" match in content: {bool(match)}')
    if match:
        print(f'  Matched: {content_lower[max(0,match.start()-50):match.end()+50]}')