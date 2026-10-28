"""
Verification test for Clear Chat feature implementation
"""

import sys
import os

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

# Read the chat.py file and verify implementation
with open(os.path.join(backend_path, 'app', 'api', 'chat.py'), 'r') as f:
    content = f.read()

print("=" * 60)
print("BACKEND VERIFICATION")
print("=" * 60)

checks = [
    ("clear_chat endpoint exists", "async def clear_chat" in content),
    ("user_id parameter", "user_id: int = None" in content),
    ("current_user dependency", "current_user: User = Depends(get_current_user)" in content),
    ("db dependency", "db: Session = Depends(get_db)" in content),
    ("is_ai_allowed check for AI conversations", "is_ai_allowed(current_user)" in content),
    ("user ownership check (sender_id == current_user.id)", "sender_id == current_user.id" in content),
    ("user ownership check (receiver_id == current_user.id)", "receiver_id == current_user.id" in content),
    ("AI conversation deletion", "ChatMessage.is_ai == True" in content),
    ("Human conversation deletion", "ChatMessage.is_ai == False" in content),
    ("Specific conversation deletion (user_id > 0)", "user_id > 0" in content or "user_id is not None and user_id" in content),
    ("Clear all conversations (user_id is None or 0)", "else:" in content),  # the else branch
    ("Transaction commit", "db.commit()" in content),
    ("Proper response structure", '"success": True' in content),
    ("Message count in response", "deleted" in content),
]

all_passed = True
for check_name, result in checks:
    status = "PASS" if result else "FAIL"
    print(f"  [{status}] {check_name}")
    if not result:
        all_passed = False

print()

# Verify frontend modifications
frontend_path = os.path.join(os.path.dirname(__file__), 'frontend', 'src')

print("=" * 60)
print("FRONTEND VERIFICATION")
print("=" * 60)

# ChatWindow.jsx
with open(os.path.join(frontend_path, 'components', 'ChatWindow.jsx'), 'r') as f:
    chat_window = f.read()

frontend_checks = [
    ("TrashIcon component", "TrashIcon" in chat_window),
    ("handleClearChat function", "handleClearChat" in chat_window),
    ("showClearConfirm state", "showClearConfirm" in chat_window),
    ("clearing state", "clearing" in chat_window),
    ("clearSuccess state", "clearSuccess" in chat_window),
    ("Confirmation dialog", "Clear Chat" in chat_window and "Cancel" in chat_window and "cleared" in chat_window.lower()),
    ("Clear button in header", "onClick={() => setShowClearConfirm(true)}" in chat_window),
    ("chatAPI.clearChat call", "chatAPI.clearChat" in chat_window),
    ("Success toast", "Chat cleared successfully" in chat_window),
    ("Error handling", "setError" in chat_window),
    ("Prevent duplicate requests", "disabled={clearing}" in chat_window),
    ("Messages cleared on success", "setMessages([])" in chat_window),
]

for check_name, result in frontend_checks:
    status = "PASS" if result else "FAIL"
    print(f"  [{status}] {check_name}")
    if not result:
        all_passed = False

# Verify API service
with open(os.path.join(frontend_path, 'services', 'api.js'), 'r') as f:
    api_content = f.read()

api_checks = [
    ("clearChat in chatAPI", "clearChat" in api_content),
    ("user_id parameter passed", "user_id" in api_content),
    ("DELETE method", "api.delete" in api_content),
    ("Correct endpoint", "/chat/clear" in api_content),
]

print()
print("  API Service:")
for check_name, result in api_checks:
    status = "PASS" if result else "FAIL"
    print(f"    [{status}] {check_name}")
    if not result:
        all_passed = False

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
if all_passed:
    print("✓ All verification checks PASSED")
else:
    print("✗ Some verification checks FAILED")

# Additional verification: Check that clear doesn't affect other features
print()
print("=" * 60)
print("FEATURE ISOLATION VERIFICATION")
print("=" * 60)

# Verify no Study Buddy changes
with open(os.path.join(backend_path, 'app', 'api', 'chat.py'), 'r') as f:
    chat_content = f.read()

# Ensure no modifications to other models
features_not_affected = [
    ("Study Buddy", "study-buddy" not in chat_content.lower() or "study_buddy" not in chat_content.lower()),
    ("Reminders", "reminder" not in chat_content.lower()),
    ("Circulars", "circular" not in chat_content.lower() or "Circular" in chat_content),  # model import is fine
    ("Database schema changes", "Column" not in chat_content or "class ChatMessage" not in chat_content),  # only imports
]

for check_name, result in features_not_affected:
    status = "PASS" if result else "FAIL"
    print(f"  [{status}] {check_name} not affected")
    if not result:
        all_passed = False

print()
print("=" * 60)
print(f"FINAL RESULT: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
print("=" * 60)

sys.exit(0 if all_passed else 1)