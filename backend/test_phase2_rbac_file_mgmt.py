"""
Validation tests for Phase 2: RBAC Hardening, Admin User Management, Audit Logs, and Bulk File Deletion.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import json
import base64
import time
import asyncio
import uuid

# Configure test environment
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Provide mock for jose and passlib if running on host environment without Docker
class MockJWTError(Exception):
    pass

class MockJWT:
    @staticmethod
    def encode(claims, key, algorithm="HS256"):
        header = base64.urlsafe_b64encode(json.dumps({"alg": algorithm, "typ": "JWT"}).encode()).decode().rstrip("=")
        serializable_claims = {}
        for k, v in claims.items():
            if hasattr(v, "timestamp"):
                serializable_claims[k] = int(v.timestamp())
            else:
                serializable_claims[k] = v
        payload = base64.urlsafe_b64encode(json.dumps(serializable_claims).encode()).decode().rstrip("=")
        sig = "mocksig"
        return f"{header}.{payload}.{sig}"

    @staticmethod
    def decode(token, key, algorithms=None):
        parts = token.split(".")
        if len(parts) != 3:
            raise MockJWTError("Invalid token format")
        if parts[2] != "mocksig":
            raise MockJWTError("Invalid signature")
        try:
            rem = len(parts[1]) % 4
            padded = parts[1] + ("=" * (4 - rem) if rem else "")
            payload_str = base64.urlsafe_b64decode(padded).decode()
            data = json.loads(payload_str)
            if "exp" in data:
                if data["exp"] < time.time():
                    raise MockJWTError("Signature has expired")
            return data
        except Exception as e:
            if isinstance(e, MockJWTError):
                raise
            raise MockJWTError(str(e))

class MockPasslibContext:
    class CryptContext:
        def __init__(self, *args, **kwargs):
            pass
        def verify(self, secret, hash_val):
            return secret == hash_val
        def hash(self, secret):
            return f"hash_{secret}"

if "jose" not in sys.modules:
    mock_jose = MagicMock()
    mock_jose.jwt = MockJWT
    mock_jose.JWTError = MockJWTError
    sys.modules["jose"] = mock_jose

if "passlib" not in sys.modules:
    mock_passlib = MagicMock()
    mock_passlib_context = MockPasslibContext()
    sys.modules["passlib"] = mock_passlib
    sys.modules["passlib.context"] = mock_passlib_context

# Provide mock modules for heavy extraction / ML libraries
for mod in ["pdfplumber", "PyPDF2", "docx", "pptx", "openpyxl", "pytesseract", "PIL", "sentence_transformers", "torch", "transformers"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from fastapi import HTTPException
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.models.file import File, FileStatus
from app.core.security import create_access_token, decode_access_token
from app.api.auth import get_current_user, get_current_active_user
from app.api.admin import require_admin, update_user_role, update_user_status
from app.api.placement import check_placement_officer_or_admin, get_student_details_for_placement
from app.api.files import bulk_delete_files
from app.schemas.file import FileBulkDeleteRequest
from app.services.audit_service import audit_service
from app.schemas.admin import UserUpdateRoleRequest, UserUpdateStatusRequest
from app.services.file_storage.file_service import file_service


class TestAuthenticationSecurity(unittest.TestCase):
    """Tests for JWT token generation, decoding, expiry, and invalid signatures."""

    def test_valid_access_token_creation_and_decoding(self):
        token = create_access_token(data={"id": 1, "sub": "admin@vcet.ac.in", "role": "admin"})
        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["id"], 1)
        self.assertEqual(payload["sub"], "admin@vcet.ac.in")
        self.assertEqual(payload["role"], "admin")
        self.assertIn("exp", payload)

    def test_expired_token_handling(self):
        expired_token = create_access_token(
            data={"id": 4, "sub": "user@vcet.ac.in", "role": "student"},
            expires_delta=timedelta(seconds=-10)
        )
        payload = decode_access_token(expired_token)
        self.assertIsNone(payload, "Expired token must return None from decode_access_token")

    def test_tampered_token_handling(self):
        token = create_access_token(data={"id": 4, "sub": "user@vcet.ac.in", "role": "student"})
        tampered = token[:-5] + "XXXXX"
        payload = decode_access_token(tampered)
        self.assertIsNone(payload, "Tampered token must return None from decode_access_token")

    def test_unauthenticated_user_dependency_fails(self):
        mock_db = MagicMock()
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token="invalid.bearer.token", db=mock_db)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("invalid", ctx.exception.detail.lower())


class TestRBACHardeningDependencies(unittest.TestCase):
    """Tests for role checking dependencies across all 5 roles."""

    def setUp(self):
        self.admin_user = User(id=1, email="admin@vcet.ac.in", role=UserRole.ADMIN, is_active=True, department="ADMIN")
        self.hod_user = User(id=2, email="hod@vcet.ac.in", role=UserRole.HOD, department="CSE", is_active=True)
        self.lecturer_user = User(id=3, email="lecturer@vcet.ac.in", role=UserRole.LECTURER, department="CSE", is_active=True)
        self.student_user = User(id=4, email="student@vcet.ac.in", role=UserRole.STUDENT, department="CSE", is_active=True)
        self.po_user = User(id=5, email="placement@vcet.ac.in", role=UserRole.PLACEMENT_OFFICER, department="PLACEMENT", is_active=True)

    def test_require_admin_permits_admin(self):
        user = require_admin(current_user=self.admin_user)
        self.assertEqual(user.id, 1)

    def test_require_admin_blocks_non_admins(self):
        for non_admin in [self.hod_user, self.lecturer_user, self.student_user, self.po_user]:
            with self.subTest(role=non_admin.role):
                with self.assertRaises(HTTPException) as ctx:
                    require_admin(current_user=non_admin)
                self.assertEqual(ctx.exception.status_code, 403)
                self.assertIn("admin", ctx.exception.detail.lower())

    def test_placement_officer_or_admin_dependency(self):
        self.assertEqual(check_placement_officer_or_admin(self.admin_user).id, 1)
        self.assertEqual(check_placement_officer_or_admin(self.po_user).id, 5)

        for denied_user in [self.hod_user, self.lecturer_user, self.student_user]:
            with self.subTest(role=denied_user.role):
                with self.assertRaises(HTTPException) as ctx:
                    check_placement_officer_or_admin(denied_user)
                self.assertEqual(ctx.exception.status_code, 403)

    def test_inactive_user_blocked_by_active_user_check(self):
        inactive_user = User(id=99, email="inactive@vcet.ac.in", role=UserRole.STUDENT, is_active=False)
        with self.assertRaises(HTTPException) as ctx:
            get_current_active_user(current_user=inactive_user)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("inactive", ctx.exception.detail.lower())


class TestStudentProfileDataSecurity(unittest.TestCase):
    """Tests for horizontal privilege escalation prevention in student profile access."""

    def test_student_cannot_access_other_student_profile(self):
        student_user = User(id=10, email="student1@vcet.ac.in", role=UserRole.STUDENT)
        mock_db = MagicMock()
        
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(get_student_details_for_placement(student_id=20, current_user=student_user, db=mock_db))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("own", ctx.exception.detail.lower())

    def test_student_can_access_own_profile(self):
        student_user = User(id=10, email="student1@vcet.ac.in", role=UserRole.STUDENT, name="Student One")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            student_user,
            None
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = asyncio.run(get_student_details_for_placement(student_id=10, current_user=student_user, db=mock_db))
        self.assertEqual(result["id"], 10)
        self.assertEqual(result["email"], "student1@vcet.ac.in")

    def test_placement_officer_and_admin_can_access_any_student_profile(self):
        po_user = User(id=5, email="po@vcet.ac.in", role=UserRole.PLACEMENT_OFFICER)
        admin_user = User(id=1, email="admin@vcet.ac.in", role=UserRole.ADMIN)
        target_student = User(id=20, email="student20@vcet.ac.in", role=UserRole.STUDENT, name="Target Student")
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            target_student, None, target_student, None
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        res1 = asyncio.run(get_student_details_for_placement(student_id=20, current_user=po_user, db=mock_db))
        self.assertEqual(res1["id"], 20)
        
        res2 = asyncio.run(get_student_details_for_placement(student_id=20, current_user=admin_user, db=mock_db))
        self.assertEqual(res2["id"], 20)


class TestAdminUserManagement(unittest.TestCase):
    """Tests for Admin User Management endpoints and safety restrictions."""

    def setUp(self):
        self.admin = User(id=1, email="admin@vcet.ac.in", name="Admin User", role=UserRole.ADMIN, is_active=True, department="ADMIN")
        self.target_user = User(id=2, email="staff@vcet.ac.in", name="Staff User", role=UserRole.LECTURER, is_active=True, department="CSE")

    def test_admin_update_user_role_success(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = self.target_user
        
        req = UserUpdateRoleRequest(role=UserRole.HOD)
        
        with patch.object(audit_service, "log_action") as mock_log:
            result = asyncio.run(update_user_role(user_id=2, request=req, current_user=self.admin, db=mock_db))
            self.assertEqual(result.role, UserRole.HOD)
            self.assertEqual(self.target_user.role, UserRole.HOD)
            mock_log.assert_called_once()
            self.assertEqual(mock_log.call_args[1]["action"], "USER_ROLE_UPDATE")

    def test_admin_cannot_demote_themselves(self):
        mock_db = MagicMock()
        req = UserUpdateRoleRequest(role=UserRole.STUDENT)
        
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(update_user_role(user_id=1, request=req, current_user=self.admin, db=mock_db))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("self-demotion", ctx.exception.detail.lower())

    def test_admin_update_user_status_success(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = self.target_user
        
        req = UserUpdateStatusRequest(is_active=False)
        
        with patch.object(audit_service, "log_action") as mock_log:
            result = asyncio.run(update_user_status(user_id=2, request=req, current_user=self.admin, db=mock_db))
            self.assertFalse(result.is_active)
            self.assertFalse(self.target_user.is_active)
            mock_log.assert_called_once()
            self.assertEqual(mock_log.call_args[1]["action"], "USER_STATUS_UPDATE")

    def test_admin_cannot_deactivate_themselves(self):
        mock_db = MagicMock()
        req = UserUpdateStatusRequest(is_active=False)
        
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(update_user_status(user_id=1, request=req, current_user=self.admin, db=mock_db))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("own account", ctx.exception.detail.lower())


class TestAdminAuditLogging(unittest.TestCase):
    """Tests for Audit Log recording, sanitization, and querying."""

    def test_audit_log_sanitizes_sensitive_fields(self):
        mock_db = MagicMock()
        actor = User(id=1, email="admin@vcet.ac.in", role=UserRole.ADMIN, department="ADMIN")
        
        unsanitized_details = {
            "password": "SuperSecretPassword123!",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "target_user": "john@vcet.ac.in",
            "new_role": "hod",
            "auth_secret": "my-secret-key"
        }
        
        entry = audit_service.log_action(
            db=mock_db,
            action="TEST_ACTION",
            actor=actor,
            target_type="user",
            target_id=2,
            outcome="SUCCESS",
            details=unsanitized_details
        )
        
        self.assertEqual(entry.details["password"], "[REDACTED]")
        self.assertEqual(entry.details["token"], "[REDACTED]")
        self.assertEqual(entry.details["auth_secret"], "[REDACTED]")
        self.assertEqual(entry.details["target_user"], "john@vcet.ac.in")
        self.assertEqual(entry.details["new_role"], "hod")
        self.assertNotIn("SuperSecretPassword123!", json.dumps(entry.details))
        mock_db.add.assert_called_once_with(entry)
        mock_db.commit.assert_called_once()

    def test_get_logs_supports_filters_and_pagination(self):
        mock_db = MagicMock()
        fake_log = AuditLog(id=1, action="USER_ROLE_CHANGE", actor_email="admin@vcet.ac.in", outcome="SUCCESS")
        query_mock = mock_db.query.return_value
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.count.return_value = 5
        query_mock.all.return_value = [fake_log]
        
        result = audit_service.get_audit_logs(
            db=mock_db,
            action="USER_ROLE_CHANGE",
            outcome="SUCCESS",
            offset=0,
            limit=10
        )
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["action"], "USER_ROLE_CHANGE")


class TestBulkFileDeletionConsistency(unittest.TestCase):
    """Tests for multi-file deletion, authorization checks, deduplication, and cleanup."""

    def setUp(self):
        self.owner = User(id=10, email="owner@vcet.ac.in", role=UserRole.LECTURER, department="CSE")
        self.other_user = User(id=20, email="intruder@vcet.ac.in", role=UserRole.STUDENT, department="ECE")
        self.admin = User(id=1, email="admin@vcet.ac.in", role=UserRole.ADMIN, department="ADMIN")

        self.fid1 = uuid.uuid4()
        self.fid2 = uuid.uuid4()
        self.file1 = File(id=self.fid1, filename="notes1.pdf", uploaded_by=10, department="CSE", status=FileStatus.ACTIVE)
        self.file2 = File(id=self.fid2, filename="notes2.pdf", uploaded_by=10, department="CSE", status=FileStatus.ACTIVE)

    def test_owner_can_bulk_delete_own_files(self):
        mock_db = MagicMock()
        with patch.object(file_service, "get_file", side_effect=lambda db, fid: self.file1 if fid == self.fid1 else self.file2), \
             patch.object(file_service, "delete_file", return_value=True) as mock_delete, \
             patch.object(audit_service, "log_action") as mock_audit:
            
            req = FileBulkDeleteRequest(file_ids=[self.fid1, self.fid2])
            res = asyncio.run(bulk_delete_files(request=req, permanent=False, current_user=self.owner, db=mock_db))
            
            self.assertEqual(res.deleted_count, 2)
            self.assertEqual(len(res.failed_ids), 0)
            mock_delete.assert_any_call(mock_db, self.fid1, False)
            mock_delete.assert_any_call(mock_db, self.fid2, False)
            mock_audit.assert_called_once()
            self.assertEqual(mock_audit.call_args[1]["action"], "FILE_BULK_DELETE")
            self.assertEqual(mock_audit.call_args[1]["outcome"], "SUCCESS")

    def test_unauthorized_user_blocked_from_deleting_others_files(self):
        mock_db = MagicMock()
        with patch.object(file_service, "get_file", return_value=self.file1), \
             patch.object(file_service, "delete_file") as mock_delete, \
             patch.object(audit_service, "log_action") as mock_audit:
            
            req = FileBulkDeleteRequest(file_ids=[self.fid1])
            res = asyncio.run(bulk_delete_files(request=req, permanent=False, current_user=self.other_user, db=mock_db))
            
            self.assertEqual(res.deleted_count, 0)
            self.assertEqual(len(res.failed_ids), 1)
            self.assertIn(self.fid1, res.failed_ids)
            mock_delete.assert_not_called()
            mock_audit.assert_called_once()
            self.assertEqual(mock_audit.call_args[1]["outcome"], "FAILURE")

    def test_duplicate_file_ids_deduplicated_safely(self):
        mock_db = MagicMock()
        with patch.object(file_service, "get_file", return_value=self.file1), \
             patch.object(file_service, "delete_file", return_value=True) as mock_delete, \
             patch.object(audit_service, "log_action"):
            
            req = FileBulkDeleteRequest(file_ids=[self.fid1, self.fid1, self.fid1])
            res = asyncio.run(bulk_delete_files(request=req, permanent=False, current_user=self.owner, db=mock_db))
            
            self.assertEqual(res.deleted_count, 1)
            self.assertEqual(mock_delete.call_count, 1)

    def test_nonexistent_files_handled_gracefully_in_partial_failure(self):
        missing_id = uuid.uuid4()
        mock_db = MagicMock()
        with patch.object(file_service, "get_file", side_effect=lambda db, fid: self.file1 if fid == self.fid1 else None), \
             patch.object(file_service, "delete_file", return_value=True) as mock_delete, \
             patch.object(audit_service, "log_action") as mock_audit:
            
            req = FileBulkDeleteRequest(file_ids=[self.fid1, missing_id])
            res = asyncio.run(bulk_delete_files(request=req, permanent=False, current_user=self.owner, db=mock_db))
            
            self.assertEqual(res.deleted_count, 1)
            self.assertEqual(len(res.failed_ids), 1)
            self.assertIn(missing_id, res.failed_ids)
            self.assertEqual(mock_delete.call_count, 1)
            mock_audit.assert_called_once()
            self.assertEqual(mock_audit.call_args[1]["outcome"], "PARTIAL_FAILURE")


if __name__ == "__main__":
    unittest.main()
