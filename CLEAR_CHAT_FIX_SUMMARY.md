Clear Chat Bug Fix - Final Summary

The critical Clear Chat bug has been FIXED and VERIFIED.

Bug: Clicking "Clear Chat" on AI conversation passed user_id=0, but backend interpreted zero as "clear ALL conversations" (both AI and human), causing unintended data loss.

Fix: New explicit API contract at DELETE /chat/clear:

| Parameter | Behavior |
|-----------|----------|
| user_id > 0 | Clear specific human conversation |
| user_id = 0 | Clear ONLY AI conversation messages (students only) |
| user_id = null + clear_all = true | Clear ALL conversations |
| user_id = null + clear_all = false | 400 Bad Request |

Files modified (3 files):
1. backend/app/api/chat.py - Endpoint with explicit contract
2. frontend/src/services/api.js - API function with clearAll parameter
3. frontend/src/components/ChatWindow.jsx - Dialog and handler updates

Verification: Static code verification of all 3 files - all 25 checks PASSED.

Placement Data Reset: COULD NOT PROCEED
- Company model has no created_by field
- create_company() service doesn't track creator
- Cannot identify agent-created vs manually created companies
- 0 company records deleted per requirements
- Student placement reset not executed (stopped at company identification)

Per instructions: "If the database does not reliably distinguish agent-created companies from manually created companies, stop and report the ambiguity rather than deleting all companies."

The Clear Chat bug fix is complete. The placement data reset was not executed.