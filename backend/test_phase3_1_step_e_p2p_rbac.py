"""
Tests for EduMatrix Phase 3.1 Step E: Role-Based P2P Chat Authorization & Communication Matrix
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.models.user import User, UserRole
from app.models.chat import ChatMessage
from app.services.chat_policy import can_chat, is_ai_allowed, is_same_department
from app.main import app
from app.core.database import SessionLocal
from app.api.auth import get_current_user


class TestPhase31StepEP2PRBAC(unittest.TestCase):
    """
    Validation Suite for Step E: Communication Matrix and Authorization.
    """

    @classmethod
    def setUpClass(cls):
        # 1. Students
        cls.student_cse = User(id=101, email="stud_cse@vcet.ac.in", name="CSE Student", role=UserRole.STUDENT, department="CSE", is_active=True)
        cls.student_ece = User(id=102, email="stud_ece@vcet.ac.in", name="ECE Student", role=UserRole.STUDENT, department="ECE", is_active=True)
        cls.student_peer_cse = User(id=103, email="peer_cse@vcet.ac.in", name="CSE Peer", role=UserRole.STUDENT, department="CSE", is_active=True)

        # 2. Lecturers
        cls.lecturer_cse = User(id=201, email="lec_cse@vcet.ac.in", name="CSE Lecturer", role=UserRole.LECTURER, department="CSE", is_active=True)
        cls.lecturer_ece = User(id=202, email="lec_ece@vcet.ac.in", name="ECE Lecturer", role=UserRole.LECTURER, department="ECE", is_active=True)

        # 3. HODs
        cls.hod_cse = User(id=301, email="hod_cse@vcet.ac.in", name="CSE HOD", role=UserRole.HOD, department="CSE", is_active=True)
        cls.hod_ece = User(id=302, email="hod_ece@vcet.ac.in", name="ECE HOD", role=UserRole.HOD, department="ECE", is_active=True)

        # 4. Placement Officer
        cls.po = User(id=401, email="po@vcet.ac.in", name="Placement Officer", role=UserRole.PLACEMENT_OFFICER, department="PLACEMENT", is_active=True)

        # 5. Admin
        cls.admin = User(id=501, email="admin@vcet.ac.in", name="Admin User", role=UserRole.ADMIN, department="ADMIN", is_active=True)

        # 6. Inactive User
        cls.inactive_user = User(id=601, email="inactive@vcet.ac.in", name="Inactive User", role=UserRole.LECTURER, department="CSE", is_active=False)

    # =========================================================================
    # A - G: STUDENT SENDER POLICY
    # =========================================================================
    def test_A_student_to_same_department_lecturer_allowed(self):
        allowed, msg = can_chat(self.student_cse, self.lecturer_cse)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")

    def test_B_student_to_different_department_lecturer_blocked(self):
        allowed, msg = can_chat(self.student_cse, self.lecturer_ece)
        self.assertFalse(allowed)

    def test_C_student_to_same_department_hod_allowed(self):
        allowed, msg = can_chat(self.student_cse, self.hod_cse)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")

    def test_D_student_to_different_department_hod_blocked(self):
        allowed, msg = can_chat(self.student_cse, self.hod_ece)
        self.assertFalse(allowed)

    def test_E_student_to_placement_officer_allowed(self):
        # Institution-wide
        allowed, msg = can_chat(self.student_cse, self.po)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")

    def test_F_student_to_student_blocked(self):
        allowed, msg = can_chat(self.student_cse, self.student_peer_cse)
        self.assertFalse(allowed)

    def test_G_student_to_admin_blocked(self):
        allowed, msg = can_chat(self.student_cse, self.admin)
        self.assertFalse(allowed)

    # =========================================================================
    # H - K: LECTURER SENDER POLICY
    # =========================================================================
    def test_H_lecturer_to_same_department_student_allowed(self):
        allowed, msg = can_chat(self.lecturer_cse, self.student_cse)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")

    def test_I_lecturer_to_different_department_student_blocked(self):
        allowed, msg = can_chat(self.lecturer_cse, self.student_ece)
        self.assertFalse(allowed)

    def test_J_lecturer_to_hod_blocked(self):
        allowed, msg = can_chat(self.lecturer_cse, self.hod_cse)
        self.assertFalse(allowed)

    def test_K_lecturer_to_placement_officer_blocked(self):
        allowed, msg = can_chat(self.lecturer_cse, self.po)
        self.assertFalse(allowed)

    # =========================================================================
    # L - P: HOD SENDER POLICY
    # =========================================================================
    def test_L_hod_to_same_department_student_allowed(self):
        allowed, msg = can_chat(self.hod_cse, self.student_cse)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")

    def test_M_hod_to_different_department_student_blocked(self):
        allowed, msg = can_chat(self.hod_cse, self.student_ece)
        self.assertFalse(allowed)

    def test_N_hod_to_same_department_lecturer_allowed(self):
        allowed, msg = can_chat(self.hod_cse, self.lecturer_cse)
        self.assertTrue(allowed)
        self.assertEqual(msg, "")

    def test_O_hod_to_different_department_lecturer_blocked(self):
        allowed, msg = can_chat(self.hod_cse, self.lecturer_ece)
        self.assertFalse(allowed)

    def test_P_hod_to_placement_officer_blocked(self):
        allowed, msg = can_chat(self.hod_cse, self.po)
        self.assertFalse(allowed)

    # =========================================================================
    # Q - S: PLACEMENT OFFICER SENDER POLICY
    # =========================================================================
    def test_Q_placement_officer_to_student_allowed(self):
        # Institution-wide: both CSE and ECE students allowed
        allowed1, _ = can_chat(self.po, self.student_cse)
        allowed2, _ = can_chat(self.po, self.student_ece)
        self.assertTrue(allowed1)
        self.assertTrue(allowed2)

    def test_R_placement_officer_to_lecturer_blocked(self):
        allowed, _ = can_chat(self.po, self.lecturer_cse)
        self.assertFalse(allowed)

    def test_S_placement_officer_to_hod_blocked(self):
        allowed, _ = can_chat(self.po, self.hod_cse)
        self.assertFalse(allowed)

    # =========================================================================
    # T: INACTIVE RECEIVER POLICY
    # =========================================================================
    def test_T_inactive_receiver_blocked(self):
        allowed, msg = can_chat(self.student_cse, self.inactive_user)
        self.assertFalse(allowed)

    # =========================================================================
    # W - Z: AI ASSISTANT ACCESS POLICY
    # =========================================================================
    def test_W_student_ai_assistant_allowed(self):
        self.assertTrue(is_ai_allowed(self.student_cse))

    def test_X_lecturer_ai_assistant_blocked(self):
        self.assertFalse(is_ai_allowed(self.lecturer_cse))

    def test_Y_hod_ai_assistant_blocked(self):
        self.assertFalse(is_ai_allowed(self.hod_cse))

    def test_Z_placement_officer_ai_assistant_blocked(self):
        self.assertFalse(is_ai_allowed(self.po))
        self.assertFalse(is_ai_allowed(self.admin))

    # =========================================================================
    # V: USER DISCOVERY /chat/users ENDPOINT FILTERING
    # =========================================================================
    def test_V_user_discovery_filtered_by_role(self):
        client = TestClient(app)

        all_mock_users = [
            self.student_cse,
            self.student_ece,
            self.student_peer_cse,
            self.lecturer_cse,
            self.lecturer_ece,
            self.hod_cse,
            self.hod_ece,
            self.po,
            self.admin
        ]

        # 1. Student discovery test
        app.dependency_overrides[get_current_user] = lambda: self.student_cse
        with patch("sqlalchemy.orm.Session.query") as mock_query:
            mock_filter = MagicMock()
            mock_filter.filter.return_value.all.return_value = [u for u in all_mock_users if u.id != self.student_cse.id]
            mock_query.return_value.filter.return_value = mock_filter

            response = client.get("/chat/users")
            self.assertEqual(response.status_code, 200)
            data = response.json()

            # Pinned AI entry should exist
            self.assertEqual(data[0]["id"], 0)
            self.assertEqual(data[0]["role"], "assistant")

            # Permitted IDs should be lecturer_cse, hod_cse, po
            human_ids = [u["id"] for u in data[1:]]
            self.assertIn(self.lecturer_cse.id, human_ids)
            self.assertIn(self.hod_cse.id, human_ids)
            self.assertIn(self.po.id, human_ids)

            # Blocked: student_ece, student_peer_cse, lecturer_ece, hod_ece, admin
            self.assertNotIn(self.student_ece.id, human_ids)
            self.assertNotIn(self.student_peer_cse.id, human_ids)
            self.assertNotIn(self.lecturer_ece.id, human_ids)
            self.assertNotIn(self.hod_ece.id, human_ids)
            self.assertNotIn(self.admin.id, human_ids)

        # 2. Lecturer discovery test
        app.dependency_overrides[get_current_user] = lambda: self.lecturer_cse
        with patch("sqlalchemy.orm.Session.query") as mock_query:
            mock_filter = MagicMock()
            mock_filter.filter.return_value.all.return_value = [u for u in all_mock_users if u.id != self.lecturer_cse.id]
            mock_query.return_value.filter.return_value = mock_filter

            response = client.get("/chat/users")
            self.assertEqual(response.status_code, 200)
            data = response.json()

            # AI assistant must NOT be present
            ids = [u["id"] for u in data]
            self.assertNotIn(0, ids)

            # Only CSE students should be present
            self.assertIn(self.student_cse.id, ids)
            self.assertIn(self.student_peer_cse.id, ids)
            self.assertNotIn(self.student_ece.id, ids)
            self.assertNotIn(self.hod_cse.id, ids)
            self.assertNotIn(self.po.id, ids)

        # Reset overrides
        app.dependency_overrides.clear()

    # =========================================================================
    # ENDPOINT AUTHORIZATION ON /chat/send
    # =========================================================================
    def test_endpoint_send_unauthorized_returns_403(self):
        client = TestClient(app)

        # Student attempting to message another student
        app.dependency_overrides[get_current_user] = lambda: self.student_cse
        with patch("sqlalchemy.orm.Session.query") as mock_query:
            # When querying receiver:
            mock_query.return_value.filter.return_value.first.return_value = self.student_peer_cse
            response = client.post("/chat/send", json={"receiver_id": self.student_peer_cse.id, "content": "Hello peer"})
            self.assertEqual(response.status_code, 403)
            self.assertIn("You are not allowed to message this user", response.json()["detail"])

        # Student attempting to message lecturer from different department
        with patch("sqlalchemy.orm.Session.query") as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = self.lecturer_ece
            response = client.post("/chat/send", json={"receiver_id": self.lecturer_ece.id, "content": "Hello"})
            self.assertEqual(response.status_code, 403)

        # Lecturer attempting to message AI Assistant
        app.dependency_overrides[get_current_user] = lambda: self.lecturer_cse
        response = client.post("/chat/send", json={"receiver_id": 0, "content": "Hello AI", "is_ai": True})
        self.assertEqual(response.status_code, 403)
        self.assertIn("AI Assistant is only available to students", response.json()["detail"])

        # Lecturer attempting to use /chat/ai
        response = client.post("/chat/ai", json={"content": "Hello AI"})
        self.assertEqual(response.status_code, 403)

        app.dependency_overrides.clear()

    # =========================================================================
    # U: WEBSOCKET POLICY ENFORCEMENT
    # =========================================================================
    def test_U_websocket_unauthorized_policy(self):
        from app.core.security import create_access_token
        client = TestClient(app)

        # 1. Student token attempting to send to another student over WebSocket
        student_token = create_access_token({"id": self.student_cse.id, "email": self.student_cse.email, "role": "student"})

        with patch("app.api.chat.SessionLocal") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session

            # Lookups in websocket: first sender (101), then receiver (103)
            user_lookups = [self.student_cse, self.student_peer_cse]
            def query_mock(model):
                q = MagicMock()
                if model == User:
                    def filter_mock(*args, **kwargs):
                        f = MagicMock()
                        if user_lookups:
                            f.first.return_value = user_lookups.pop(0)
                        else:
                            f.first.return_value = None
                        return f
                    q.filter.side_effect = filter_mock
                return q

            mock_session.query.side_effect = query_mock

            with client.websocket_connect(f"/chat/ws/{student_token}") as websocket:
                websocket.send_text('{"receiver_id": 103, "content": "Unauthorized student chat"}')
                received = websocket.receive_text()
                import json
                resp_json = json.loads(received)
                self.assertEqual(resp_json["type"], "error")
                self.assertEqual(resp_json["code"], 403)
                self.assertIn("You are not allowed to message this user", resp_json["message"])

        # 2. Lecturer attempting to send to AI over WebSocket
        lecturer_token = create_access_token({"id": self.lecturer_cse.id, "email": self.lecturer_cse.email, "role": "lecturer"})

        with patch("app.api.chat.SessionLocal") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = self.lecturer_cse

            with client.websocket_connect(f"/chat/ws/{lecturer_token}") as websocket:
                websocket.send_text('{"receiver_id": 0, "content": "Lecturer to AI", "is_ai": true}')
                received = websocket.receive_text()
                import json
                resp_json = json.loads(received)
                self.assertEqual(resp_json["type"], "error")
                self.assertEqual(resp_json["code"], 403)
                self.assertIn("AI Assistant is only available to students", resp_json["message"])


if __name__ == "__main__":
    unittest.main()
